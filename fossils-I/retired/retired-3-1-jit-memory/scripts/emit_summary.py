#!/usr/bin/env python3
"""Reduce a JS_INSTR_DIR of per-process JSONL into a compact JIT-memory summary."""

import collections
import hashlib
import json
import os
import sys

SKIP = ('"kind":"ic-instance-attach"',
        '"kind":"ic-instance-detach"',
        '"kind":"entries-flush"')

# Engine-blob owners: source is a per-owner constant (there is no
# separate IR for these; the "source" is the C++ generator path baked
# into the firefox binary). Two blobs of the same owner in different
# procs, produced by the same binary, share a source by construction.
ENGINE_BLOB_OWNERS = ("baseline-interpreter", "trampoline", "shared-ic")

CHECKPOINTS = ("Start", "StartSettled", "TabsOpen", "TabsOpenSettled",
               "TabsOpenForceGC", "TabsClosed", "TabsClosedExtra",
               "TabsClosedSettled", "TabsClosedForceGC")


def die(msg):
    print(f"emit_summary: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def engine_source_sha(owner):
    """Stable per-owner source_sha for engine blobs. Constant across
    all instances in every proc of the same binary — the definition of
    'achievable to share'."""
    h = hashlib.sha1()
    h.update(b"engine-blob/")
    h.update(owner.encode("ascii"))
    return h.hexdigest()


class Proc:
    __slots__ = ("pid", "kind", "epoch", "markers", "live",
                 "created", "finalized", "bl", "icb_src", "icb_code",
                 "icb_bytes", "rx", "cls")

    def __init__(self, pid, kind, epoch):
        self.pid = pid
        self.kind = kind
        self.epoch = epoch
        self.markers = []
        self.live = []
        # code_local_id -> (create_ts, bytes, owner, code_sha)
        self.created = {}
        # code_local_id -> finalize_ts
        self.finalized = {}
        # script_local_id / other lookups
        self.cls = {}
        # code_local_id -> (semantic_id, script_local_id, method_bytes,
        #                   code_id)
        self.bl = {}
        # source_sha -> {code_sha, machine_bytes, cache_kind}
        self.icb_src = {}
        # regexp instances: list of (source_sha, code_sha, bytes)
        self.rx = []
        # kept for compat with older records tests
        self.icb_code = {}
        self.icb_bytes = {}


def parse(path):
    p = None
    pending = collections.defaultdict(list)
    with open(path) as f:
        for ln in f:
            if any(s in ln for s in SKIP):
                continue
            o = json.loads(ln)
            k = o["kind"]
            if k == "run-header":
                p = Proc(o["pid"], o["proc"], o["wall_us_epoch"])
                continue
            if p is None:
                continue
            t = p.epoch + o["ts_us"]
            if k == "jitcode-create":
                code_sha = o.get("code_sha")
                p.created[o["code_local_id"]] = (t, o["bytes"], o["owner"],
                                                 code_sha)
                if o["owner"] == "baseline-script":
                    pending[(o["tid"], o["bytes"])].append(o["code_local_id"])
            elif k == "jitcode-finalize":
                p.finalized[o["code_local_id"]] = t
            elif k == "baseline-compile":
                q = pending.get((o["tid"], o["method_bytes"]))
                if q:
                    cid = q.pop()
                    p.bl[cid] = (o["semantic_id"], o["script_local_id"],
                                 o["method_bytes"], o.get("code_id"))
            elif k == "script-create":
                p.cls[o["script_local_id"]] = o["source_class"]
            elif k == "ic-body-emit":
                # source_sha is the new, correct name; fall back to
                # ic_body_id for backward compatibility with pre-rename
                # records so mixed corpora don't crash.
                src = o.get("source_sha") or o["ic_body_id"]
                p.icb_src[src] = {
                    "code_sha": o.get("code_sha"),
                    "machine_bytes": o.get("machine_bytes", 0),
                    "cache_kind": o.get("cache_kind", "?"),
                }
            elif k == "regexp-emit":
                p.rx.append({
                    "source_sha": o["source_sha"],
                    "code_sha": o["code_sha"],
                    "bytes": o["machine_bytes"],
                })
            elif k == "snapshot-marker":
                p.markers.append((t, o["marker"]))
            elif k == "snapshot-live":
                by = {d["owner"]: d["code_bytes"] for d in o["by_owner"]}
                p.live.append((t, by, o["live_mmap_bytes"],
                               o["distinct_ic_body_bytes"]))
    return p


def cluster(procs):
    par = max((p for p in procs if p.kind == "parent"),
              key=lambda p: len(p.markers))
    if not par.markers:
        die("parent process has zero snapshot-marker events")
    return [{"index": i, "name": CHECKPOINTS[i] if i < len(CHECKPOINTS) else m,
             "abs_us": t}
            for i, (t, m) in enumerate(sorted(par.markers))]


def assign(procs, cks, tol_us=20_000_000):
    ts = [c["abs_us"] for c in cks]
    sel = [{} for _ in cks]
    for p in procs:
        for s in p.live:
            i = min(range(len(ts)), key=lambda j: abs(ts[j] - s[0]))
            if abs(ts[i] - s[0]) > tol_us:
                continue
            cur = sel[i].get(p.pid)
            if cur is None or abs(ts[i] - s[0]) < abs(ts[i] - cur[0]):
                sel[i][p.pid] = s
    return sel


def live_ids(p, t):
    out = []
    for cid, rec in p.created.items():
        ct, b, ow, csha = rec
        if ct > t:
            continue
        ft = p.finalized.get(cid)
        if ft is not None and ft <= t:
            continue
        out.append((cid, b, ow, csha))
    return out


def summarize(procs):
    cks = cluster(procs)
    sel = assign(procs, cks)

    per_ck = []
    for ci, c in enumerate(cks):
        rows = []
        for p in procs:
            s = sel[ci].get(p.pid)
            if s is None:
                continue
            rows.append({
                "pid": p.pid,
                "kind": p.kind,
                "abs_us": s[0],
                "live_by_owner": s[1],
                "mmap_bytes": s[2],
                "distinct_ic_body_bytes": s[3],
            })
        per_ck.append({**c, "procs": rows})

    peak = max(per_ck, key=lambda r: sum(
        sum(pr["live_by_owner"].values()) for pr in r["procs"]))
    peak_ci = peak["index"]

    per_proc_at_peak = []
    for p in procs:
        s = sel[peak_ci].get(p.pid)
        if s is None:
            continue
        t = s[0]

        engine_blobs = []
        baseline_alive = []
        ic_alive = []
        for cid, b, ow, csha in live_ids(p, t):
            if ow in ENGINE_BLOB_OWNERS:
                engine_blobs.append({
                    "owner": ow,
                    "source_sha": engine_source_sha(ow),
                    "code_sha": csha,
                    "bytes": b,
                })
            elif ow == "baseline-script":
                r = p.bl.get(cid)
                if r is None:
                    continue
                sid, sclid, tb, code_id = r
                sc = p.cls.get(sclid, "unknown")
                baseline_alive.append({
                    "source_sha": sid,
                    "code_sha": code_id,
                    "source_class": sc,
                    "bytes": tb,
                })
            elif ow == "baseline-ic":
                # A jitcode-create for baseline-ic carries the compiled
                # body's code_sha. Join to the CacheIR source_sha via
                # ic-body-emit's icb_src map by matching code_sha.
                pass

        # Live IC bodies: use ic-body-emit records directly. Each
        # (source_sha, code_sha) pair is one distinct compiled body in
        # this proc at some point; we attribute machine_bytes as the
        # body's live bytes (the JitCode is kept alive by the interner
        # for the life of the JitZone).
        for src, rec in p.icb_src.items():
            if not rec.get("code_sha"):
                continue
            ic_alive.append({
                "source_sha": src,
                "code_sha": rec["code_sha"],
                "bytes": rec["machine_bytes"],
                "cache_kind": rec["cache_kind"],
            })

        live_bl = s[1].get("baseline-script", 0)
        if live_bl > 0 and not baseline_alive:
            die(f"pid {p.pid}: live baseline-script bytes ({live_bl}) but "
                f"empty baseline_alive; (tid,method_bytes) join failed")
        live_ic = s[1].get("baseline-ic", 0)
        if live_ic > 0 and not ic_alive:
            die(f"pid {p.pid}: live baseline-ic bytes ({live_ic}) but no "
                f"ic-body-emit records with code_sha; instrumentation may "
                f"be missing the code_sha field (rebuild required)")

        per_proc_at_peak.append({
            "pid": p.pid,
            "kind": p.kind,
            "engine_blobs": engine_blobs,
            "baseline_alive": baseline_alive,
            "ic_alive": ic_alive,
            "regexp_alive": p.rx,
        })

    return {
        "n_processes": len(procs),
        "n_parent": sum(1 for p in procs if p.kind == "parent"),
        "checkpoints": per_ck,
        "peak_checkpoint_index": peak_ci,
        "per_proc_at_peak": per_proc_at_peak,
    }


def main(root):
    procs = []
    for fn in sorted(os.listdir(root)):
        if fn.endswith(".jsonl"):
            p = parse(os.path.join(root, fn))
            if p:
                procs.append(p)
    if not procs:
        die(f"no valid .jsonl files in {root}")
    json.dump(summarize(procs), sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
