#!/usr/bin/env python3
"""Break the JIT memory summary down into per-checkpoint totals and a peak-checkpoint breakdown."""

import collections
import json
import sys


def load_summary():
    obs = json.load(sys.stdin)
    obs_list = obs.get("observations", [obs])
    ob = obs_list[0]
    out = ob.get("stdout")
    if isinstance(out, list):
        out = "\n".join(out)
    return json.loads(out.strip())


def per_checkpoint(summary):
    rows = []
    for c in summary["checkpoints"]:
        by = collections.Counter()
        mmap = 0
        n = 0
        for pr in c["procs"]:
            n += 1
            mmap += pr["mmap_bytes"]
            for k, v in pr["live_by_owner"].items():
                by[k] += v
        rows.append({
            "index": c["index"],
            "name": c["name"],
            "n_procs": n,
            "code_bytes": sum(by.values()),
            "mmap_bytes": mmap,
            "by_owner": dict(by),
        })
    return rows


def peak_breakdown(summary):
    peak_ci = summary["peak_checkpoint_index"]
    ck = summary["checkpoints"][peak_ci]
    n = len(ck["procs"])

    by = collections.Counter()
    mmap = 0
    for pr in ck["procs"]:
        mmap += pr["mmap_bytes"]
        for k, v in pr["live_by_owner"].items():
            by[k] += v
    code = sum(by.values())

    # Cast (deterministic-inclusion vs distributional) is the paper's
    # core split. Deterministic inclusion is the fixed engine blob every
    # process regenerates before executing any script: interpreter,
    # trampolines, shared IC.
    FIXED = ("baseline-interpreter", "trampoline", "shared-ic")
    fixed_bytes = sum(by[o] for o in FIXED)

    return {
        "checkpoint": ck["name"],
        "n_procs": n,
        "code_bytes": code,
        "mmap_bytes": mmap,
        "slack_bytes": mmap - code,
        "by_owner": [
            {
                "owner": o,
                "bytes": v,
                "share": v / code if code else 0.0,
                "per_proc_bytes": v / n if n else 0.0,
            }
            for o, v in by.most_common()
        ],
        "deterministic_inclusion": {
            "owners": list(FIXED),
            "bytes": fixed_bytes,
            "share": fixed_bytes / code if code else 0.0,
            "per_proc_bytes": fixed_bytes / n if n else 0.0,
        },
    }


def fixed_blob(summary):
    """Per-process fixed engine blob: (owner, size) variants counted
    across processes. Grouping by size stands in for content identity;
    processes with the same size for the same owner get the same
    bit-image."""
    peak_ci = summary["peak_checkpoint_index"]
    per = summary["per_proc_at_peak"]

    variants = collections.Counter()
    procs_with_variant = collections.defaultdict(set)
    per_proc_bytes = collections.Counter()
    for pr in per:
        for v in pr["fixed_variants"]:
            key = (v["owner"], v["bytes"])
            variants[key] += v["bytes"]
            procs_with_variant[key].add(pr["pid"])
            per_proc_bytes[pr["pid"]] += v["bytes"] * v["count"]

    resident = sum(per_proc_bytes.values())
    distinct_one_copy = sum(k[1] for k in variants)
    n_paying = sum(1 for v in per_proc_bytes.values() if v > 0)
    recoverable = resident - distinct_one_copy
    return {
        "resident_bytes": resident,
        "procs_paying": n_paying,
        "per_proc_median_bytes": (
            sorted(per_proc_bytes.values())[len(per_proc_bytes) // 2]
            if per_proc_bytes else 0),
        "distinct_variants": len(variants),
        "distinct_one_copy_bytes": distinct_one_copy,
        "recoverable_bytes": recoverable,
        "recoverable_share": recoverable / resident if resident else 0.0,
        "top_variants": [
            {"owner": k[0], "bytes": k[1],
             "n_procs": len(procs_with_variant[k]),
             "resident_bytes": v}
            for k, v in sorted(variants.items(), key=lambda x: -x[1])[:8]
        ],
    }


def cross_process(summary):
    """Baseline-script residency broken by source_class: self-hosted vs
    guest+chrome. The paper wants the self-hosted redundancy figure,
    which measures deterministic sharing at the *method* level rather
    than the engine-blob level."""
    per = summary["per_proc_at_peak"]

    self_ids = {}
    self_res = 0
    guest_ids = {}
    guest_res = 0
    for pr in per:
        seen = {}
        for b in pr["baseline_alive"]:
            sid = b["semantic_id"]
            # Intra-process duplicates counted separately; here take one
            # copy per (pid, semantic_id) to isolate the cross-process
            # axis.
            if sid in seen:
                continue
            seen[sid] = (b["bytes"], b["source_class"])
        for sid, (byt, sc) in seen.items():
            if sc == "self-hosted":
                self_ids[sid] = byt
                self_res += byt
            else:
                guest_ids[sid] = byt
                guest_res += byt

    def frac(res, ids):
        d = sum(ids.values())
        return {
            "resident_bytes": res,
            "distinct_bytes": d,
            "duplicate_bytes": res - d,
            "duplicate_share": (res - d) / res if res else 0.0,
        }

    return {
        "self_hosted": frac(self_res, self_ids),
        "guest_plus_chrome": frac(guest_res, guest_ids),
    }


def intra_process(summary):
    """Same source compiled once per realm inside one process."""
    per = summary["per_proc_at_peak"]
    live = distinct = 0
    per_proc = []
    for pr in per:
        m = collections.defaultdict(int)
        first = {}
        for b in pr["baseline_alive"]:
            sid = b["semantic_id"]
            m[sid] += b["bytes"]
            first.setdefault(sid, b["bytes"])
        e = sum(m.values())
        d = sum(first.values())
        if e:
            live += e
            distinct += d
            per_proc.append({"pid": pr["pid"], "live_bytes": e,
                             "dup_bytes": e - d})
    per_proc.sort(key=lambda r: -r["dup_bytes"])
    return {
        "n_compiling_procs": len(per_proc),
        "live_baseline_bytes": live,
        "distinct_bytes": distinct,
        "duplicate_bytes": live - distinct,
        "duplicate_share": (live - distinct) / live if live else 0.0,
        "worst": per_proc[:5],
    }


def main():
    summary = load_summary()
    result = {
        "n_processes": summary["n_processes"],
        "n_parent": summary["n_parent"],
        "checkpoints": per_checkpoint(summary),
        "peak": peak_breakdown(summary),
        "fixed_blob_at_peak": fixed_blob(summary),
        "cross_process_at_peak": cross_process(summary),
        "intra_process_at_peak": intra_process(summary),
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
