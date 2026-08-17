#!/usr/bin/env python3
"""Per-observation normalizer for 7-11 (Speedometer 3 memory).

Consumes the emit_summary.py blob from stdin; produces the fossil metric
tree for the two synthetic checkpoints Peak and Final."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "parse_memory"

BUCKETS = (
    "libxul_exec", "libxul_rodata", "libxul_rw",
    "anon_exec", "anon_rw", "other_file", "other_anon",
)

PRIMARY_CHECKPOINTS = ("Peak", "Final")

CONTRACT = {
    "default":        {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": False},
    "default-no-ion": {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": True},
    "aot":            {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": False, "no_ion": False},
    "aot-corpus":     {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": True,  "no_ion": False},
}


def kind_of(variant):
    if variant == "default-no-ion":
        return "default-no-ion"
    if variant == "default":
        return "default"
    if variant == "aot-corpus":
        return "aot-corpus"
    if variant == "aot":
        return "aot"
    manifest.fail(PREFIX, f"unclassified variant {variant!r}")


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command", "")
    if variant not in CONTRACT:
        manifest.fail(PREFIX, f"unknown variant {variant!r}")
    c = CONTRACT[variant]
    if c["binary"] not in command:
        manifest.fail(PREFIX, f"{variant}: expected binary fragment {c['binary']!r}")
    if c["mc"] not in command:
        manifest.fail(PREFIX, f"{variant}: expected mozconfig fragment {c['mc']!r}")
    has_aot_only = "JIT_OPTION_aotOnly=1" in command or "JIT_OPTION_aotOnly=true" in command
    if c["aot_only"] and not has_aot_only:
        manifest.fail(PREFIX, f"{variant}: JIT_OPTION_aotOnly not present")
    if not c["aot_only"] and has_aot_only:
        manifest.fail(PREFIX, f"{variant}: forbidden JIT_OPTION_aotOnly present")
    has_no_ion = "JIT_OPTION_ion=0" in command or "javascript.options.ion=false" in command
    if c["no_ion"] and not has_no_ion:
        manifest.fail(PREFIX, f"{variant}: no-Ion flag not present")
    if not c["no_ion"] and has_no_ion:
        manifest.fail(PREFIX, f"{variant}: forbidden no-Ion flag present")
    return variant


def to_mb(kb):
    return round(kb / 1024.0, 4)


def zero_bucket_mb():
    return {
        "size_mb": 0.0, "rss_mb": 0.0, "pss_mb": 0.0,
        "shared_clean_mb": 0.0, "shared_dirty_mb": 0.0,
        "private_clean_mb": 0.0, "private_dirty_mb": 0.0,
        "referenced_mb": 0.0, "anonymous_mb": 0.0,
        "uss_mb": 0.0, "vma_count": 0,
    }


def bucket_kb_to_mb(bkt):
    return {
        "size_mb":         to_mb(bkt.get("size_kb", 0)),
        "rss_mb":          to_mb(bkt.get("rss_kb", 0)),
        "pss_mb":          to_mb(bkt.get("pss_kb", 0)),
        "shared_clean_mb": to_mb(bkt.get("shared_clean_kb", 0)),
        "shared_dirty_mb": to_mb(bkt.get("shared_dirty_kb", 0)),
        "private_clean_mb":to_mb(bkt.get("private_clean_kb", 0)),
        "private_dirty_mb":to_mb(bkt.get("private_dirty_kb", 0)),
        "referenced_mb":   to_mb(bkt.get("referenced_kb", 0)),
        "anonymous_mb":    to_mb(bkt.get("anonymous_kb", 0)),
        "uss_mb":          to_mb(bkt.get("uss_kb", 0)),
        "vma_count":       int(bkt.get("vma_count", 0)),
    }


def sum_buckets(buckets_list):
    out = zero_bucket_mb()
    for b in buckets_list:
        for k in out:
            out[k] += b.get(k, 0)
    for k in out:
        if k != "vma_count":
            out[k] = round(out[k], 4)
    return out


def reduce_checkpoint(cp):
    procs = cp.get("procs", [])
    content = [p for p in procs if p.get("kind") == "content"]

    per_proc = {}
    for p in content:
        buckets_mb = {b: bucket_kb_to_mb(p.get("buckets", {}).get(b, {}))
                      for b in BUCKETS}
        ae = buckets_mb["anon_exec"]
        lx = buckets_mb["libxul_exec"]
        per_proc[f"pid_{p['pid']}"] = {
            "pid": p["pid"],
            "anon_exec_pss_mb": ae["pss_mb"],
            "anon_exec_rss_mb": ae["rss_mb"],
            "libxul_exec_pss_mb": lx["pss_mb"],
            "libxul_exec_rss_mb": lx["rss_mb"],
        }

    totals = {}
    for b in BUCKETS:
        rows = [bucket_kb_to_mb(p.get("buckets", {}).get(b, {})) for p in content]
        totals[b] = sum_buckets(rows)

    engine_pss = totals["anon_exec"]["pss_mb"] + totals["libxul_exec"]["pss_mb"]
    engine_rss = totals["anon_exec"]["rss_mb"] + totals["libxul_exec"]["rss_mb"]
    engine_uss = totals["anon_exec"]["uss_mb"] + totals["libxul_exec"]["uss_mb"]

    n = len(content)
    per_proc_engine_pss = round(engine_pss / n, 4) if n else 0.0

    return {
        "n_content_procs": n,
        "n_parent_procs": cp.get("n_parent_procs", 0),
        "engine_pss_mb": round(engine_pss, 4),
        "engine_rss_mb": round(engine_rss, 4),
        "engine_uss_mb": round(engine_uss, 4),
        "per_proc_engine_pss_mb": per_proc_engine_pss,
        "totals": totals,
        "per_proc": per_proc,
    }


def main():
    m = manifest.load(PREFIX)
    variant = validate_manifest(m)
    kind = kind_of(variant)

    obs = json.load(sys.stdin)
    stdout = obs.get("stdout")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    if not isinstance(stdout, str) or not stdout.strip():
        manifest.fail(PREFIX, "observation stdout is empty; emit_summary produced nothing")
    try:
        summary = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        manifest.fail(PREFIX, f"observation stdout is not JSON: {e}")

    warnings = list(summary.get("warnings", []))
    checkpoints = summary.get("checkpoints", [])
    reduced = {}
    for cp in checkpoints:
        name = cp.get("name") or cp.get("marker")
        reduced[name] = reduce_checkpoint(cp)

    primary = {name: reduced[name] for name in PRIMARY_CHECKPOINTS if name in reduced}
    anchor_name = "Peak" if "Peak" in primary else ("Final" if "Final" in primary else None)
    if anchor_name is None:
        manifest.fail(PREFIX, "no primary checkpoint present")
    anchor = primary[anchor_name]

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

    sample = {
        "kind": kind,
        "anchor_checkpoint": anchor_name,
        "n_content_procs": anchor["n_content_procs"],
        "engine_pss_mb": anchor["engine_pss_mb"],
        "engine_rss_mb": anchor["engine_rss_mb"],
        "engine_uss_mb": anchor["engine_uss_mb"],
        "per_proc_engine_pss_mb": anchor["per_proc_engine_pss_mb"],
        "checkpoints": primary,
    }
    output = {
        **sample,
        "runs": {f"run_{iteration:02d}": sample},
        "meta": {
            "variant": variant,
            "kind": kind,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations", 0),
            "warnings": warnings[:20],
            "n_engine_procs_ever": summary.get("n_engine_procs_ever", 0),
            "n_sidecar_procs_ever": summary.get("n_sidecar_procs_ever", 0),
            "n_intervals": summary.get("n_intervals", 0),
            "peak_interval": summary.get("peak_interval"),
            "final_interval": summary.get("final_interval"),
        },
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
