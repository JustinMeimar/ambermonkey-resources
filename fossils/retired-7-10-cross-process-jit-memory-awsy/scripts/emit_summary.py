#!/usr/bin/env python3
"""Reduce sidecar smaps samples + AWSY memory reports into one observation
JSON blob, printed on stdout. Consumed by analyses/parse_memory.py.

The AOT branch does not have JS_INSTR/JitInstrReporter, so no engine JSONL
is expected. All sampling is external via the sidecar.

Input: $D (AWSY --results dir + sidecar/ subdir).
"""

import collections
import gzip
import json
import re
import sys
from pathlib import Path


BUCKETS = (
    "libxul_exec", "libxul_rodata", "libxul_rw",
    "anon_exec", "anon_rw", "other_file", "other_anon",
)

METRICS = (
    "size_kb", "rss_kb", "pss_kb",
    "shared_clean_kb", "shared_dirty_kb",
    "private_clean_kb", "private_dirty_kb",
    "referenced_kb", "anonymous_kb",
)

PID_LABEL = re.compile(r"\(pid (\d+)[,)]")


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


def marker_short_name(marker):
    """'TabsOpenForceGC:0' -> ('TabsOpenForceGC', 0). Falls back to (marker, None)."""
    if ":" in marker:
        head, _, tail = marker.partition(":")
        if tail.isdigit():
            return head, int(tail)
    return marker, None


def load_pid_registry(sidecar_dir):
    """Returns dict[(pid,starttime)] -> {"kind","cmd","first_ts","vanish_ts"}."""
    reg = {}
    log = sidecar_dir / "pids.jsonl"
    if not log.exists():
        return reg
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (row.get("pid"), row.get("starttime"))
        if row.get("event") == "discover":
            reg[key] = {
                "kind": row.get("kind"),
                "cmd": row.get("cmd", ""),
                "first_ts": row.get("ts_us"),
                "vanish_ts": None,
            }
        elif row.get("event") == "vanish" and key in reg:
            reg[key]["vanish_ts"] = row.get("ts_us")
    return reg


def load_sidecar_smaps(sidecar_dir):
    """Group sidecar smaps files by marker. Returns dict[marker] -> list of sample dicts."""
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
        grouped[sample["marker"]].append(sample)
    return grouped


def bucket_sample(sample):
    """Given one sidecar sample (per-pid smaps), returns dict[bucket] -> bucket-metrics."""
    out = {b: empty_bucket() for b in BUCKETS}
    for vma in sample.get("vmas", []):
        b = bucket_of(vma.get("path", ""), vma.get("perms", ""))
        add_vma(out[b], vma)
    return out


def load_memory_reports(dir_path):
    """Return dict[(checkpoint,iteration)] -> {pids_seen, total_processes,
    whole_browser_explicit_bytes} for cross-checking context. This does NOT
    depend on JitInstrReporter (AOT branch); we only look at the standard
    Firefox memory reporters."""
    out = {}
    for path in sorted(dir_path.glob("memory-report-*.json.gz")):
        stem = path.name[len("memory-report-"):-len(".json.gz")]
        name, _, iter_s = stem.rpartition("-")
        if not name or not iter_s.isdigit():
            continue
        pids = set()
        explicit = 0
        try:
            with gzip.open(path, "rb") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        for report in data.get("reports", []):
            p = report.get("path", "")
            proc = report.get("process", "")
            m = PID_LABEL.search(proc)
            if m:
                pids.add(int(m.group(1)))
            if p == "explicit":
                explicit += report.get("amount", 0)
        out[(name, int(iter_s))] = {
            "pids_seen": sorted(pids),
            "n_processes_in_report": len(pids),
            "explicit_total_bytes": explicit,
        }
    return out


def load_perfherder(dir_path):
    path = dir_path / "perfherder-data.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def summarize(dir_path):
    sidecar_dir = dir_path / "sidecar"
    if not sidecar_dir.exists():
        die(f"no sidecar/ directory in {dir_path}; sidecar failed to start")

    registry = load_pid_registry(sidecar_dir)
    sidecar_meta_path = sidecar_dir / "meta.json"
    sidecar_meta = json.loads(sidecar_meta_path.read_text()) if sidecar_meta_path.exists() else {}
    sidecar_samples = load_sidecar_smaps(sidecar_dir)
    reports = load_memory_reports(dir_path)
    perfherder = load_perfherder(dir_path)

    warnings = list(sidecar_meta.get("warnings", []))
    if not sidecar_samples:
        warnings.append("sidecar produced zero smaps samples; no memory-report-*.json.gz files "
                        "appeared during the run (AWSY may have failed early)")

    checkpoints = []
    for marker, samples in sidecar_samples.items():
        name, iteration = marker_short_name(marker)
        procs = []
        content_count = 0
        parent_count = 0
        for sample in samples:
            pid = sample["pid"]
            starttime = sample.get("starttime")
            kind = sample.get("kind", "other")
            if kind == "content":
                content_count += 1
            elif kind == "parent":
                parent_count += 1
            reg = registry.get((pid, starttime))
            buckets = bucket_sample(sample) if not sample.get("error") else {b: empty_bucket() for b in BUCKETS}
            procs.append({
                "pid": pid,
                "starttime": starttime,
                "kind": kind,
                "cmd_hint": (reg or {}).get("cmd", sample.get("cmd", "")),
                "sample_lag_us": sample.get("sample_ts_us", 0) - sample.get("marker_ts_us", 0),
                "sample_error": sample.get("error"),
                "buckets": buckets,
            })
        # Cross-check against AWSY memory report: PIDs that the reporter saw
        # but the sidecar didn't sample (usually means proc died between
        # sidecar's PID discovery poll and its smaps read).
        report = reports.get((name, iteration or 0))
        report_pids = set(report["pids_seen"]) if report else set()
        sidecar_pids = {p["pid"] for p in procs}
        missing = sorted(report_pids - sidecar_pids)
        if missing:
            warnings.append(
                f"marker {marker}: {len(missing)} pids in AWSY memory-report "
                f"but not in sidecar samples: {missing[:8]}"
            )
        checkpoints.append({
            "marker": marker,
            "name": name,
            "iteration": iteration,
            "marker_ts_us": samples[0].get("marker_ts_us") if samples else None,
            "n_content_procs": content_count,
            "n_parent_procs": parent_count,
            "n_procs_sampled": len(procs),
            "report_pids_missing_from_sidecar": missing,
            "procs": procs,
            "awsy_report": report,
        })

    checkpoints.sort(key=lambda c: c["marker_ts_us"] or 0)

    result = {
        "schema_version": 1,
        "run_dir": str(dir_path),
        "sidecar_meta": {k: v for k, v in sidecar_meta.items() if k != "warnings"},
        "n_sidecar_procs_ever": len(registry),
        "markers_seen": [c["marker"] for c in checkpoints],
        "checkpoints": checkpoints,
        "warnings": warnings,
    }
    if perfherder is not None:
        result["perfherder"] = perfherder
    return result


def main():
    if len(sys.argv) != 2:
        die("usage: emit_summary.py <run-dir>")
    dir_path = Path(sys.argv[1])
    if not dir_path.exists():
        die(f"{dir_path} does not exist")
    print(json.dumps(summarize(dir_path)))


if __name__ == "__main__":
    main()
