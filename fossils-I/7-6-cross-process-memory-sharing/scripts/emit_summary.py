#!/usr/bin/env python3
"""emit_summary for Speedometer 3 memory: reads interval-sampled smaps files
written by smaps_sidecar.py and emits two synthetic checkpoints per run:

    Peak   — the interval whose content-proc engine PSS (anon_exec + libxul_exec)
             is maximum. Represents the workload at its hottest point.
    Final  — the last-emitted interval, i.e. steady state as Speedometer wraps.

The output shape mirrors 7-10's emit_summary so parse_memory can consume it
without special-casing. All samples are kept in the JSON for post-hoc analysis.
"""

import collections
import gzip
import json
import os
import platform
import re
import sys
from pathlib import Path


BUCKETS = ("libxul_exec", "libxul_rodata", "libxul_rw",
           "anon_exec", "anon_rw", "other_file", "other_anon")

METRICS = ("size_kb", "rss_kb", "pss_kb", "shared_clean_kb", "shared_dirty_kb",
           "private_clean_kb", "private_dirty_kb", "referenced_kb", "anonymous_kb")

INTERVAL_RE = re.compile(r"^interval:(?P<n>\d+)$")


def die(msg):
    print(f"emit_summary: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def bucket_of(path, perms):
    is_libxul = path.endswith("libxul.so")
    x = "x" in perms
    w = "w" in perms
    if is_libxul and x:
        return "libxul_exec"
    if is_libxul and w:
        return "libxul_rw"
    if is_libxul:
        return "libxul_rodata"
    if path == "" and x:
        return "anon_exec"
    if path == "" and perms == "rw-p":
        return "anon_rw"
    if path == "":
        return "other_anon"
    return "other_file"


def empty_bucket():
    b = {m: 0 for m in METRICS}
    b["vma_count"] = 0
    b["uss_kb"] = 0
    return b


def add_vma(bucket, vma):
    for m in METRICS:
        bucket[m] += vma.get(m, 0)
    bucket["vma_count"] += 1
    bucket["uss_kb"] += vma.get("private_clean_kb", 0) + vma.get("private_dirty_kb", 0)


def bucket_sample(sample):
    out = {b: empty_bucket() for b in BUCKETS}
    for vma in sample.get("vmas", []):
        b = bucket_of(vma.get("path", ""), vma.get("perms", ""))
        add_vma(out[b], vma)
    return out


def load_sidecar_samples(sidecar_dir):
    """Return dict[interval_n] -> list of {pid, kind, cmd, buckets, ...}."""
    smaps_dir = sidecar_dir / "smaps"
    grouped = collections.defaultdict(list)
    if not smaps_dir.exists():
        return grouped
    for path in sorted(smaps_dir.iterdir()):
        if not path.name.endswith(".json"):
            continue
        try:
            sample = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        marker = sample.get("marker", "")
        m = INTERVAL_RE.match(marker)
        if not m:
            continue
        n = int(m.group("n"))
        buckets = (bucket_sample(sample)
                   if not sample.get("error")
                   else {b: empty_bucket() for b in BUCKETS})
        grouped[n].append({
            "pid": sample.get("pid"),
            "starttime": sample.get("starttime"),
            "kind": sample.get("kind", "other"),
            "cmd_hint": sample.get("cmd", ""),
            "sample_lag_us": sample.get("sample_ts_us", 0) - sample.get("marker_ts_us", 0),
            "sample_error": sample.get("error"),
            "buckets": buckets,
        })
    return grouped


def content_engine_pss_kb(procs):
    total = 0
    for p in procs:
        if p.get("kind") != "content":
            continue
        b = p.get("buckets", {})
        total += b.get("anon_exec", {}).get("pss_kb", 0)
        total += b.get("libxul_exec", {}).get("pss_kb", 0)
    return total


def content_count(procs):
    return sum(1 for p in procs if p.get("kind") == "content")


def parent_count(procs):
    return sum(1 for p in procs if p.get("kind") == "parent")


def main():
    if len(sys.argv) != 2:
        die("usage: emit_summary.py DIR")
    dir_path = Path(sys.argv[1])
    if not dir_path.exists():
        die(f"missing dir: {dir_path}")

    sidecar_dir = dir_path / "sidecar"
    if not sidecar_dir.exists():
        die(f"no sidecar/ dir under {dir_path}; sidecar failed to start")

    sidecar_meta_path = sidecar_dir / "meta.json"
    sidecar_meta = (json.loads(sidecar_meta_path.read_text())
                    if sidecar_meta_path.exists() else {})
    warnings = list(sidecar_meta.get("warnings", []))

    intervals = load_sidecar_samples(sidecar_dir)
    if not intervals:
        die("sidecar produced no interval samples; check --interval-ms and "
            "that content procs matched --parent-exe")

    checkpoints = []
    peak_n = max(intervals, key=lambda n: content_engine_pss_kb(intervals[n]))
    final_n = max(intervals)
    for name, n in (("Peak", peak_n), ("Final", final_n)):
        procs = intervals[n]
        checkpoints.append({
            "marker": f"interval:{n}",
            "name": name,
            "iteration": None,
            "marker_ts_us": None,
            "n_content_procs": content_count(procs),
            "n_parent_procs": parent_count(procs),
            "n_procs_sampled": len(procs),
            "procs": procs,
        })

    all_pids_ever = set()
    for procs in intervals.values():
        for p in procs:
            all_pids_ever.add(p.get("pid"))
    n_engine_procs_ever = sum(
        1 for procs in intervals.values() for p in procs
        if p.get("kind") == "content"
    )

    result = {
        "schema_version": 1,
        "run_dir": str(dir_path),
        "sidecar_meta": {k: v for k, v in sidecar_meta.items() if k != "warnings"},
        "markers_seen": [c["marker"] for c in checkpoints],
        "checkpoints": checkpoints,
        "warnings": warnings,
        "n_engine_procs_ever": len({p.get("pid") for procs in intervals.values()
                                    for p in procs if p.get("kind") == "content"}),
        "n_sidecar_procs_ever": len(all_pids_ever),
        "n_intervals": len(intervals),
        "peak_interval": peak_n,
        "final_interval": final_n,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
