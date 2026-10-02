#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Freeze training specializations and challenge them with held-out IC traces."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


FORMAT = "specialization-cache-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def process(event):
    return event["run"], event["pid"], event["process_start_us"]


def instance(event):
    return (*process(event), event["ic_script"])


def compilation(event):
    return (*process(event), event["compilation"])


def read_events(paths):
    events = []
    seen = set()
    for path in paths:
        with open(path, encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("version") != 1 or "run" not in event:
                    raise ValueError(f"{path}:{line_no}: not an extracted v1 event")
                key = (*process(event), event["sequence"])
                if key in seen:
                    raise ValueError(f"{path}:{line_no}: duplicate event {key}")
                seen.add(key)
                events.append(event)
    # Process-local sequence numbers survive wall-clock adjustment. No causal
    # ordering between processes is inferred from their wall-clock timestamps.
    return sorted(events, key=lambda e: (*process(e), e["sequence"]))


def extract(args):
    for path in args.logs:
        with open(path, encoding="utf-8", errors="strict") as stream:
            for line_no, line in enumerate(stream, 1):
                _, marker, payload = line.partition("SPCACHE\t")
                if not marker:
                    continue
                event = json.loads(payload)
                if event.get("event") == "lost":
                    raise ValueError(f"{path}:{line_no}: engine dropped a trace record")
                if event.get("version") != 1:
                    raise ValueError(f"{path}:{line_no}: unsupported trace version")
                event["run"] = args.run
                print(json.dumps(event))


def projection(stub):
    return {
        "kind": stub["kind"],
        "ir": stub["ir"],
        "type_data": stub["type_data"],
        "fields": [
            {"type": f["type"], "bits": f["bits"] if f["scalar"] else None,
             "layout": f.get("layout")}
            for f in stub["fields"]
        ],
    }


def obstacles(stub):
    result = Counter(f["type"] for f in stub["fields"] if not f["scalar"])
    for op in stub["ops"]:
        if any(word in op for word in ("Shape", "Fuse", "Specific", "Script", "Call")):
            result[f"op:{op}"] += 1
    return result


def collect(events):
    scripts = {}
    compiles = defaultdict(lambda: {"profiles": [], "selected": [], "phases": []})
    histories = defaultdict(list)
    for event in events:
        if event["event"] == "script":
            key = instance(event)
            if key in scripts:
                raise ValueError(f"duplicate script lifetime: {key}")
            scripts[key] = event
        if "ic_script" in event:
            histories[instance(event)].append(event)
        if event.get("compilation"):
            state = compiles[compilation(event)]
            kind = event["event"]
            if kind == "ion_request":
                state["request"] = event
            elif kind == "ion_link":
                state["link"] = event
            elif kind == "ion_compile":
                state["phases"].append(event)
            elif kind == "profile":
                state["profiles"].append(event)
            elif kind == "selected":
                state["selected"].append(event)
            elif kind == "dependencies":
                state["dependencies"] = event["types"]
            elif kind in ("bailout", "invalidate"):
                state.setdefault(kind, []).append(event)
    for key in histories:
        if key not in scripts:
            raise ValueError(f"missing script definition for {key}; trace is incomplete")
    return scripts, compiles, histories


def eligible(script, provenance):
    kind = ("self_hosted" if script["self_hosted"] else
            "system" if script["system_realm"] else "guest")
    return script["source_encoding"] != 0 and (provenance == "all" or kind == provenance)


def train(args):
    events = read_events(args.traces)
    scripts, compiles, _ = collect(events)
    builds = {(e["build_id"], e["pointer_bytes"]) for e in events}
    if len(builds) != 1 or next(iter(builds))[0] == "unspecified":
        raise ValueError("training requires one explicit build id and pointer size")
    build, pointer_bytes = next(iter(builds))
    candidates = defaultdict(dict)
    compiled_keys = set()
    script_runs = defaultdict(set)
    for script in scripts.values():
        if eligible(script, args.provenance) and not script["inlined"]:
            script_runs[script["key"]].add(script["run"])
    for state in compiles.values():
        request, link = state.get("request"), state.get("link")
        if not request or not link or not link["success"]:
            continue
        script = scripts[instance(request)]
        if not eligible(script, args.provenance):
            continue
        compiled_keys.add(script["key"])
        root_profiles = [p for p in state["profiles"] if instance(p) == instance(request)]
        if not root_profiles:
            continue
        profile = root_profiles[0]
        selected = [s for s in state["selected"] if instance(s) == instance(request)]
        sites = {str(s["offset"]): [projection(stub) for stub in s["stubs"]]
                 for s in selected}
        if not sites:
            continue
        dependencies = sorted(state.get("dependencies", []))
        inline_keys = sorted(scripts[instance(p)]["key"] for p in state["profiles"]
                             if instance(p) != instance(request))
        signature = canonical([sites, dependencies, inline_keys])
        variant_id = hashlib.sha256(signature.encode()).hexdigest()
        if variant_id not in candidates[script["key"]]:
            candidates[script["key"]][variant_id] = {
                "id": variant_id, "sites": sites, "dependencies": dependencies,
                "inline_keys": inline_keys, "training_instances": 0,
                "training_runs": set(), "backend_us": [], "code_bytes": [],
                "observed_bailouts": 0, "observed_invalidations": 0,
                "obstacles": Counter(), "filename": script["filename"],
                "warmup": [], "unselected_sites": len(profile["sites"]) - len(sites),
            }
        variant = candidates[script["key"]][variant_id]
        variant["training_instances"] += 1
        variant["training_runs"].add(script["run"])
        variant["backend_us"].append(sum(p["duration_us"] for p in state["phases"]
                                         if p["phase"] == "backend" and p["success"]))
        variant["code_bytes"].append(link["code_bytes"])
        variant["warmup"].append(request["warmup"])
        variant["observed_bailouts"] += len(state.get("bailout", []))
        variant["observed_invalidations"] += len(state.get("invalidate", []))
        for site in selected:
            for stub in site["stubs"]:
                variant["obstacles"].update(obstacles(stub))
    result = {}
    for key, versions in candidates.items():
        if len(script_runs[key]) < args.min_runs:
            continue
        ranked = sorted(versions.values(), key=lambda v: (-len(v["training_runs"]),
                                                         -v["training_instances"], v["id"]))
        result[key] = ranked[:args.variants]
        for variant in result[key]:
            variant["training_runs"] = sorted(variant["training_runs"])
            variant["backend_us_median"] = statistics.median(variant.pop("backend_us"))
            variant["code_bytes_median"] = statistics.median(variant.pop("code_bytes"))
    manifest = {
        "format": FORMAT, "build_id": build, "pointer_bytes": pointer_bytes,
        "training_runs": sorted({e["run"] for e in events}),
        "provenance": args.provenance, "max_variants": args.variants,
        "selection": "training run frequency, then compilation frequency",
        "scripts": result,
        "hint_keys": sorted(key for key in compiled_keys
                            if len(script_runs[key]) >= args.min_runs),
        "interpretation": "CacheIR projections; opaque fields require rebinding and validation",
    }
    Path(args.output).write_text(json.dumps(manifest, indent=2) + "\n")
    if args.hints:
        lines = [f"SMHINTS 1 {build}"]
        lines.extend(f"{key} {args.threshold}" for key in manifest["hint_keys"])
        Path(args.hints).write_text("\n".join(lines) + "\n")


def compatible_projection(observed, expected):
    for key in ("kind", "ir", "type_data"):
        if observed[key] != expected[key]:
            return False
    if len(observed["fields"]) != len(expected["fields"]):
        return False
    for a, b in zip(observed["fields"], expected["fields"]):
        if (a["type"], a["bits"]) != (b["type"], b["bits"]):
            return False
        if a.get("layout") is not None and b.get("layout") is not None:
            if a["layout"] != b["layout"]:
                return False
    return True


def site_conflict(site, expected):
    if str(site["offset"]) not in expected:
        return None
    allowed = expected[str(site["offset"])]
    for stub in site["stubs"]:
        if not any(compatible_projection(projection(stub), s) for s in allowed):
            return {"offset": site["offset"], "reason": "new_cacheir_projection",
                    "ops": stub["ops"]}
    return None


def evaluate(args):
    manifest = json.loads(Path(args.manifest).read_text())
    if manifest["format"] != FORMAT:
        raise ValueError("unsupported manifest")
    events = read_events(args.traces)
    if set(e["run"] for e in events) & set(manifest["training_runs"]):
        raise ValueError("training/evaluation run overlap; use independent recordings")
    if any((e["build_id"], e["pointer_bytes"]) !=
           (manifest["build_id"], manifest["pointer_bytes"]) for e in events):
        raise ValueError("evaluation build or architecture differs from training")
    scripts, compiles, histories = collect(events)
    by_owner = defaultdict(list)
    for state in compiles.values():
        if state.get("request"):
            by_owner[instance(state["request"])].append(state)
    counts = Counter()
    rows = []
    totals = Counter()
    for ident, script in scripts.items():
        if script["inlined"] or not eligible(script, manifest["provenance"]):
            continue
        counts["eligible_instances"] += 1
        variants = manifest["scripts"].get(script["key"], [])
        if not variants:
            counts["unseen_key"] += 1
            continue
        counts["training_key_matches"] += 1
        alive = {v["id"] for v in variants}
        observed = defaultdict(set)
        conflicts = []
        fallback_samples = 0
        for event in histories[ident]:
            if event["event"] not in ("ic", "profile"):
                continue
            if event.get("reason") == "fallback":
                fallback_samples += 1
            for site in event["sites"]:
                if site["stubs"]:
                    for v in variants:
                        if str(site["offset"]) in v["sites"]:
                            observed[v["id"]].add(str(site["offset"]))
                for variant in variants:
                    if variant["id"] not in alive:
                        continue
                    conflict = site_conflict(site, variant["sites"])
                    if conflict:
                        alive.remove(variant["id"])
                        conflicts.append({**conflict, "variant": variant["id"],
                                          "timestamp_us": event["timestamp_us"],
                                          "warmup": event.get("warmup")})
        first = variants[0]
        first_survives = first["id"] in alive
        fully_observed = [v for v in variants if v["id"] in alive and
                          observed[v["id"]] == set(v["sites"])]
        counts["first_variant_no_observed_conflict"] += first_survives
        counts["any_variant_no_observed_conflict"] += bool(alive)
        counts["any_variant_all_selected_sites_observed"] += bool(fully_observed)
        counts["all_variants_conflicted"] += not alive
        own_compiles = by_owner[ident]
        backend_us = sum(p["duration_us"] for c in own_compiles for p in c["phases"]
                         if p["phase"] == "backend")
        oracle_us = sum(p["duration_us"] for c in own_compiles for p in c["phases"]
                        if p["phase"] == "oracle")
        link_us = sum(c.get("link", {}).get("duration_us", 0) for c in own_compiles)
        totals["backend_us_at_training_keys"] += backend_us
        totals["oracle_us_at_training_keys"] += oracle_us
        totals["link_us_at_training_keys"] += link_us
        if fully_observed:
            totals["backend_us_at_projection_survivors"] += backend_us
        links = [c["link"] for c in own_compiles if c.get("link", {}).get("success")]
        first_link = min((e["timestamp_us"] for e in links), default=None)
        rows.append({
            "instance": ident, "key": script["key"], "filename": script["filename"],
            "first_variant_survives": first_survives,
            "surviving_variants": sorted(alive), "conflicts": conflicts,
            "selected_sites_observed": {k: len(v) for k, v in observed.items()},
            "fully_observed_survivors": [v["id"] for v in fully_observed],
            "fallback_samples": fallback_samples,
            "observed_ion_compilations": len(own_compiles),
            "observed_bailouts": sum(e["event"] == "bailout" for e in histories[ident]),
            "observed_invalidations": sum(e["event"] == "invalidate" for e in histories[ident]),
            "backend_us": backend_us, "oracle_us": oracle_us, "link_us": link_us,
            "jit_script_to_first_ion_link_us":
                first_link - script["timestamp_us"] if first_link is not None else None,
            "lifetime_end_observed": any(e["event"] == "end" for e in histories[ident]),
        })
    report = {
        "format": FORMAT, "counts": counts, "work_weights": totals, "instances": rows,
        "limits": [
            "Projection agreement is not predicted guard success or validated native-code identity.",
            "Any-variant results use hindsight selection among frozen training variants.",
            "Only recorded IC states are challenged; optimized execution and unobserved values are censored.",
            "Bailouts/invalidations are from the actual local compilation, not the training artifact.",
            "Compilation durations are work weights; time to link includes idle time and is not latency saved.",
            "Inlined dependencies and optimizer-introduced guards are not validated by root IC agreement.",
        ],
    }
    print(json.dumps(report, indent=2))


def compare(args):
    samples = defaultdict(list)
    seen = set()
    for path in args.timings:
        for line in Path(path).read_text().splitlines():
            item = json.loads(line)
            key = item["workload"], item["condition"], item["run"]
            if key in seen or item["elapsed_ms"] <= 0:
                raise ValueError(f"duplicate or invalid timing: {key}")
            seen.add(key)
            samples[key[:2]].append(item["elapsed_ms"])
    rows = []
    for (workload, condition), values in sorted(samples.items()):
        baseline = samples.get((workload, args.baseline))
        if not baseline:
            raise ValueError(f"missing baseline for {workload}")
        reference = statistics.median(baseline)
        median = statistics.median(values)
        rows.append({"workload": workload, "condition": condition, "runs": len(values),
                     "median_ms": median, "min_ms": min(values), "max_ms": max(values),
                     "median_delta_ms": reference - median,
                     "median_reduction_percent": 100 * (reference - median) / reference})
    print(json.dumps({"results": rows, "interpretation":
                     "Descriptive independent-run timings; no significance claim."}, indent=2))


def positive(value):
    number = int(value)
    if not 1 <= number <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("expected an integer in [1, 2**32-1]")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("extract")
    p.add_argument("--run", required=True)
    p.add_argument("logs", nargs="+")
    p.set_defaults(action=extract)
    p = commands.add_parser("train")
    p.add_argument("traces", nargs="+")
    p.add_argument("--output", required=True)
    p.add_argument("--hints")
    p.add_argument("--threshold", type=positive, default=1)
    p.add_argument("--variants", type=positive, default=1)
    p.add_argument("--min-runs", type=positive, default=2)
    p.add_argument("--provenance", choices=("guest", "system", "self_hosted", "all"), default="guest")
    p.set_defaults(action=train)
    p = commands.add_parser("evaluate")
    p.add_argument("--manifest", required=True)
    p.add_argument("traces", nargs="+")
    p.set_defaults(action=evaluate)
    p = commands.add_parser("compare")
    p.add_argument("--baseline", default="default")
    p.add_argument("timings", nargs="+")
    p.set_defaults(action=compare)
    args = parser.parse_args()
    try:
        args.action(args)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
