#!/usr/bin/env python3
"""Headline JIT memory numbers from one AWSY tp6 record."""

import collections
import json
import sys

MB = 1024.0 * 1024.0
FIXED = ("baseline-interpreter", "trampoline", "shared-ic")


def load_summary():
    obs = json.load(sys.stdin)
    obs_list = obs.get("observations", [obs])
    ob = obs_list[0]
    out = ob.get("stdout")
    if isinstance(out, list):
        out = "\n".join(out)
    return json.loads(out.strip())


def peak(summary):
    ci = summary["peak_checkpoint_index"]
    ck = summary["checkpoints"][ci]
    by = collections.Counter()
    mmap = 0
    for pr in ck["procs"]:
        mmap += pr["mmap_bytes"]
        for k, v in pr["live_by_owner"].items():
            by[k] += v
    return ck, by, mmap


def fixed_blob(summary, n_procs):
    variants = collections.Counter()
    per_proc_bytes = collections.Counter()
    for pr in summary["per_proc_at_peak"]:
        for v in pr["fixed_variants"]:
            variants[(v["owner"], v["bytes"])] += 1
            per_proc_bytes[pr["pid"]] += v["bytes"] * v["count"]
    resident = sum(per_proc_bytes.values())
    distinct_one_copy = sum(k[1] for k in variants)
    recoverable = resident - distinct_one_copy
    return {
        "mb_per_proc": (resident / len(per_proc_bytes) / MB
                        if per_proc_bytes else 0.0),
        "distinct_variants": len(variants),
        "resident_mb_browser_wide": resident / MB,
        "recoverable_mb_browser_wide": recoverable / MB,
        "recoverable_share": recoverable / resident if resident else 0.0,
    }


def intra_process(summary):
    live = distinct = 0
    per_proc_shares = []
    for pr in summary["per_proc_at_peak"]:
        first = {}
        m = collections.defaultdict(int)
        for b in pr["baseline_alive"]:
            sid = b["semantic_id"]
            m[sid] += b["bytes"]
            first.setdefault(sid, b["bytes"])
        e = sum(m.values())
        d = sum(first.values())
        if e:
            live += e
            distinct += d
            per_proc_shares.append((e - d) / e)
    per_proc_shares.sort(reverse=True)
    return {
        "resident_mb_browser_wide": live / MB,
        "distinct_mb_browser_wide": distinct / MB,
        "duplicate_mb_browser_wide": (live - distinct) / MB,
        "duplicate_share": (live - distinct) / live if live else 0.0,
        "worst_proc_dup_share": per_proc_shares[0] if per_proc_shares else 0.0,
    }


def inter_process_baseline(summary):
    def bucket():
        return {"ids": {}, "resident": 0}
    b = {"self_hosted": bucket(), "guest_plus_chrome": bucket()}
    for pr in summary["per_proc_at_peak"]:
        seen = {}
        for a in pr["baseline_alive"]:
            sid = a["semantic_id"]
            if sid in seen:
                continue
            seen[sid] = (a["bytes"], a["source_class"])
        for sid, (byt, sc) in seen.items():
            key = "self_hosted" if sc == "self-hosted" else "guest_plus_chrome"
            b[key]["ids"][sid] = byt
            b[key]["resident"] += byt

    def frac(x):
        d = sum(x["ids"].values())
        r = x["resident"]
        return {
            "resident_mb": r / MB,
            "distinct_mb": d / MB,
            "duplicate_mb": (r - d) / MB,
            "duplicate_share": (r - d) / r if r else 0.0,
        }
    return {"self_hosted": frac(b["self_hosted"]),
            "guest_plus_chrome": frac(b["guest_plus_chrome"])}


def main():
    s = load_summary()
    ck, by, mmap = peak(s)
    n_procs = len(ck["procs"])
    code = sum(by.values())

    fb = fixed_blob(s, n_procs)
    ip = intra_process(s)
    xp = inter_process_baseline(s)

    per_proc_mb = code / n_procs / MB if n_procs else 0.0
    # Recoverable = fixed-blob cross-proc dedup + intra-process dedup +
    # inter-process baseline dedup (self-hosted + guest). Amortized per
    # process to line up with the paper's per-process framing.
    recoverable_mb_per_proc = (
        (fb["recoverable_mb_browser_wide"]
         + ip["duplicate_mb_browser_wide"]
         + xp["self_hosted"]["duplicate_mb"]
         + xp["guest_plus_chrome"]["duplicate_mb"])
        / n_procs) if n_procs else 0.0

    out = {
        "corpus": {
            "n_processes_ever": s["n_processes"],
            "n_procs_at_peak": n_procs,
            "peak_checkpoint": ck["name"],
        },
        "peak_jit_footprint": {
            "code_mb_browser_wide": code / MB,
            "mmap_mb_browser_wide": mmap / MB,
            "code_mb_per_proc": per_proc_mb,
        },
        "fixed_blob": fb,
        "intra_process_baseline": ip,
        "inter_process_baseline": xp,
        "recoverable_total": {
            "mb_per_proc": recoverable_mb_per_proc,
            "share_of_jit_code": (recoverable_mb_per_proc / per_proc_mb
                                  if per_proc_mb else 0.0),
        },
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
