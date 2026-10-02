#!/usr/bin/env python3

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys


SCOPE_ORDER = ("first", "same_runtime", "same_process", "cross_process")


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0}

    def percentile(p):
        position = (len(values) - 1) * p
        lower = int(position)
        fraction = position - lower
        return values[lower] + fraction * (values[min(lower + 1, len(values) - 1)] - values[lower])

    return {
        "count": len(values),
        "min": values[0],
        "p25": percentile(0.25),
        "median": percentile(0.5),
        "p75": percentile(0.75),
        "p90": percentile(0.9),
        "p99": percentile(0.99),
        "max": values[-1],
        "mean": statistics.fmean(values),
    }


def provenance_summary(events):
    groups = {}
    for event in events:
        if event["event"] != "install":
            continue
        group = groups.setdefault(event["provenance"], {
            "installs": 0, "fingerprinted_installs": 0, "pids": set(),
            "seen": {}, "relaxed_seen": {}, "repeats": 0,
            "cross_process_repeats": 0,
        })
        group["installs"] += 1
        group["fingerprinted_installs"] += bool(event["key_has_source"])
        group["pids"].add(event["pid"])
        key = tuple(event["cache_key"])
        prior_pids = group["seen"].setdefault(key, set())
        group["repeats"] += bool(prior_pids)
        group["cross_process_repeats"] += bool(prior_pids - {event["pid"]})
        prior_pids.add(event["pid"])
        if event["key_has_source"]:
            relaxed_key = (event["source_hash"], event["source_encoding"],
                           event["bytecode_hash"], event["immutable_flags"],
                           event["debug_instrumentation"])
            group["relaxed_seen"].setdefault(relaxed_key, set()).add(event["pid"])
    return {name: {
        "installs": group["installs"],
        "fingerprinted_installs": group["fingerprinted_installs"],
        "pids": sorted(group["pids"]),
        "keys": len(group["seen"]),
        "repeat_installs": group["repeats"],
        "cross_process_keys": sum(len(pids) > 1 for pids in group["seen"].values()),
        "cross_process_repeats": group["cross_process_repeats"],
        "relaxed_cross_process_keys": sum(len(pids) > 1 for pids in group["relaxed_seen"].values()),
    } for name, group in groups.items()}


def analyze_record(path, observation=None):
    manifest = json.loads((path / "manifest.json").read_text())
    results = ({"observations": [observation]} if observation is not None else
               json.loads((path / "results.json").read_text()))
    events = []
    if len(results["observations"]) != 1:
        raise ValueError("analyze each observation separately; process addresses cannot span recordings")
    for observation in results["observations"]:
        for line in observation["stdout"]:
            event = json.loads(line)
            event["iteration"] = observation["iteration"]
            event["original_order"] = len(events)
            events.append(event)
    summaries = [event for event in events if event["event"] == "summary"]
    if len(summaries) != 1:
        raise ValueError(f"expected one recording summary: {path}")
    events.sort(key=lambda event: (event.get("timestamp_us", float("inf")), event["original_order"]))

    seen = {}
    key_rows = {}
    source_rows = defaultdict(lambda: {"installs": 0, "repeats": 0, "cache_bytes": 0})
    compile_by_script = {}
    install_by_baseline = {}
    counts = Counter()
    scopes = Counter()
    compile_times = []
    candidate_compile_times = []
    cache_sizes = []
    recurrence_gaps = []
    lifetimes = []
    linked_compiles = 0
    matched_discards = 0
    run_start = next(e["timestamp_us"] for e in events if e["event"] == "run")

    for index, event in enumerate(events):
        event["event_index"] = index
        event["elapsed_us"] = event.get("timestamp_us", run_start) - run_start
        kind = event["event"]
        counts[kind] += 1

        if kind == "compile":
            if event["success"]:
                compile_times.append(event["duration_us"])
                compile_by_script[(event["pid"], event["script"])] = index
            continue
        if kind == "discard":
            install_index = install_by_baseline.pop((event["pid"], event["baseline"]), None)
            event["install_event_index"] = install_index
            if install_index is not None:
                matched_discards += 1
                lifetime = event["timestamp_us"] - events[install_index]["timestamp_us"]
                if lifetime >= 0:
                    event["lifetime_us"] = lifetime
                    events[install_index]["discard_event_index"] = index
                    lifetimes.append(lifetime)
            continue
        if kind != "install":
            continue

        install_by_baseline[(event["pid"], event["baseline"])] = index
        compile_index = compile_by_script.pop((event["pid"], event["script"]), None)
        event["compile_event_index"] = compile_index
        compile_us = None
        if compile_index is not None:
            linked_compiles += 1
            compile_us = events[compile_index]["duration_us"]
            event["compile_us"] = compile_us
            events[compile_index]["install_event_index"] = index

        if event["provenance"] != "guest" or not event["key_has_source"]:
            continue

        key = tuple(event["cache_key"])
        prior = seen.get(key)
        if prior is None:
            scope = "first"
        elif prior["pid"] == event["pid"] and prior["runtime"] == event["runtime"]:
            scope = "same_runtime"
        elif prior["pid"] == event["pid"]:
            scope = "same_process"
        else:
            scope = "cross_process"
        scopes[scope] += 1
        event["recurrence_scope"] = scope
        event["previous_install_event_index"] = prior["index"] if prior else None
        if prior:
            gap = event["timestamp_us"] - prior["timestamp_us"]
            event["recurrence_gap_us"] = gap
            recurrence_gaps.append(gap)
        seen[key] = {"pid": event["pid"], "runtime": event["runtime"],
                     "timestamp_us": event["timestamp_us"], "index": index}

        row = key_rows.get(key)
        if row is None:
            row = {"id": len(key_rows), "cache_key": event["cache_key"],
                   "filename": event["filename"], "first_event_index": index,
                   "last_event_index": index, "installs": 0, "pids": set(),
                   "runtimes": set(), "cache_bytes_min": event["cache_bytes"],
                   "cache_bytes_max": event["cache_bytes"], "compile_us": 0,
                   "cache_bytes_first": event["cache_bytes"],
                   "code_bytes_first": event["code_bytes"],
                   "allocated_code_bytes_first": event["allocated_code_bytes"],
                   "linked_compiles": 0}
            key_rows[key] = row
        event["key_id"] = row["id"]
        row["installs"] += 1
        row["last_event_index"] = index
        row["pids"].add(event["pid"])
        row["runtimes"].add((event["pid"], event["runtime"]))
        row["cache_bytes_min"] = min(row["cache_bytes_min"], event["cache_bytes"])
        row["cache_bytes_max"] = max(row["cache_bytes_max"], event["cache_bytes"])
        if compile_us is not None:
            row["linked_compiles"] += 1
            row["compile_us"] += compile_us
            candidate_compile_times.append(compile_us)
        cache_sizes.append(event["cache_bytes"])

        source = source_rows[event["filename"]]
        source["installs"] += 1
        source["repeats"] += scope != "first"
        source["cache_bytes"] += event["cache_bytes"]

    rows = []
    for row in key_rows.values():
        row["pids"] = sorted(row["pids"])
        row["runtime_count"] = len(row.pop("runtimes"))
        row["repeat_installs"] = row["installs"] - 1
        rows.append(row)
    summary = next((event for event in events if event["event"] == "summary"), {})
    if summary.get("exit_code", summary.get("raptor_exit_code")) != 0 or not summary.get("log_files"):
        raise ValueError(f"incomplete browser recording: {path}")
    installs = [event for event in events if event["event"] == "install"
                and "key_id" in event]
    variable_keys = {row["id"] for row in rows
                     if row["cache_bytes_min"] != row["cache_bytes_max"]}
    return {
        "record_id": path.name,
        "manifest": manifest,
        "observation_count": len(results["observations"]),
        "recording": summary,
        "counts": dict(counts),
        "provenance_summary": provenance_summary(events),
        "candidate": {
            "installs": sum(scopes.values()),
            "keys": len(rows),
            "recurrence_scope": {scope: scopes[scope] for scope in SCOPE_ORDER},
            "linked_compiles": len(candidate_compile_times),
            "variable_size_keys": sum(row["cache_bytes_min"] != row["cache_bytes_max"] for row in rows),
            "variable_size_repeats": sum(event["key_id"] in variable_keys
                                         and event["recurrence_scope"] != "first"
                                         for event in installs),
        },
        "event_links": {"compiled_installs": linked_compiles,
                        "matched_discards": matched_discards},
        "distributions": {
            "successful_compile_us": distribution(compile_times),
            "candidate_compile_us": distribution(candidate_compile_times),
            "candidate_cache_bytes": distribution(cache_sizes),
            "recurrence_gap_us": distribution(recurrence_gaps),
            "installed_lifetime_us": distribution(lifetimes),
            "installs_per_key": distribution([row["installs"] for row in rows]),
        },
        "top_sources": [{"filename": name, **data} for name, data in
                        sorted(source_rows.items(), key=lambda pair: pair[1]["repeats"], reverse=True)[:30]],
        "keys": rows,
        "events": events,
    }


def main():
    observation = json.load(sys.stdin)
    result = analyze_record(Path(sys.argv[2]), observation)
    json.dump({key: result[key] for key in
               ("counts", "candidate", "event_links", "distributions",
                "provenance_summary",
                "top_sources")}, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
