#!/usr/bin/env python3
"""Peak-snapshot JIT residency per class, split into three bands:
currently_shared (already bit-identical across procs), achievable_shared
(same source but process-specific addresses), unique (irreducible residue).
Ion is reported as a class total only; there is no per-band hash instrumentation for it.
"""

import collections
import json
import sys


def die(msg):
    print(f"shareability: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def load_summary():
    obs = json.load(sys.stdin)
    ob = obs.get("observations", [obs])[0]
    out = ob.get("stdout")
    if isinstance(out, list):
        out = "\n".join(out)
    return json.loads(out.strip())


def three_band(instances, ground_total):
    """Compute (currently_shared, achievable_shared, unique) for one
    class given a list of {source_sha, code_sha, bytes} instances across
    all procs. Scales the band-decomposition to ground_total so per-class
    totals reconcile with the snapshot-live tally."""
    if not instances:
        return (0, 0, 0)
    for i in instances:
        if not i.get("code_sha") or not i.get("source_sha"):
            die(f"instance missing code_sha or source_sha: {i}")

    # Group by code_sha: bytes should agree within a group (code_sha is
    # SHA over the compiled bytes), so pick the first as canonical.
    by_code = {}
    for i in instances:
        c = i["code_sha"]
        if c not in by_code:
            by_code[c] = {"source_sha": i["source_sha"],
                          "bytes": i["bytes"], "count": 0}
        by_code[c]["count"] += 1

    total = sum(i["bytes"] for i in instances)
    currently_shared = sum(
        (g["count"] - 1) * g["bytes"] for g in by_code.values())
    remaining = total - currently_shared

    # Group code-collapsed representatives by source_sha. Canonical size
    # = max bytes across variants (an upper bound on the size the shared
    # copy must be to accommodate all callers).
    by_src = collections.defaultdict(list)
    for c, g in by_code.items():
        by_src[g["source_sha"]].append(g["bytes"])

    unique = sum(max(byts) for byts in by_src.values())
    achievable_shared = sum(sum(byts) - max(byts) for byts in by_src.values())

    # Sanity: currently_shared + achievable_shared + unique should equal
    # total exactly. Round-off is impossible (integer arithmetic), so any
    # mismatch is a real accounting bug.
    if currently_shared + achievable_shared + unique != total:
        die(f"three_band accounting mismatch: "
            f"cs={currently_shared} as={achievable_shared} u={unique} "
            f"sum={currently_shared+achievable_shared+unique} total={total}")

    # Reconcile against ground truth (snapshot-live per-owner tally).
    # Instances come from class-specific event streams; snapshot-live is
    # the JitCode-registry tally. Small drift is normal (async ordering
    # of jitcode-create vs. class events). Scale proportionally so the
    # visualized total matches the ground-truth live figure.
    if total > 0 and ground_total > 0:
        scale = ground_total / total
        if abs(scale - 1.0) > 0.30:
            die(f"three_band reconstruction/ground ratio {scale:.3f} "
                f"differs from 1.0 by >30%; join is dropping too many "
                f"events (total={total}, ground={ground_total})")
        currently_shared = round(currently_shared * scale)
        achievable_shared = round(achievable_shared * scale)
        unique = round(unique * scale)
        # Fix rounding drift to keep the sum equal to ground.
        drift = ground_total - (currently_shared + achievable_shared + unique)
        unique += drift
    return (currently_shared, achievable_shared, unique)


def main():
    s = load_summary()
    ci = s["peak_checkpoint_index"]
    ck = s["checkpoints"][ci]

    total_by_owner = collections.Counter()
    for pr in ck["procs"]:
        for k, v in pr["live_by_owner"].items():
            total_by_owner[k] += v
    n_procs = len(ck["procs"])
    if n_procs == 0:
        die("peak checkpoint has zero procs")

    per = s["per_proc_at_peak"]

    # Bucket instances by class. Each class -> list of instance dicts.
    # Engine blobs collapse to their owner name; baseline-script splits
    # by source_class (self-hosted / guest-chrome) because the paper's
    # narrative separates them.
    buckets = collections.defaultdict(list)

    for pr in per:
        for b in pr["engine_blobs"]:
            buckets[b["owner"]].append(b)
        for b in pr["baseline_alive"]:
            sc = "self-hosted" if b["source_class"] == "self-hosted" \
                else "guest-chrome"
            buckets[f"baseline-script:{sc}"].append(b)
        for b in pr["ic_alive"]:
            buckets["baseline-ic"].append(b)
        for b in pr["regexp_alive"]:
            buckets["regexp"].append(b)

    # Class -> owner name for ground-truth reconciliation.
    OWNER_OF = {
        "baseline-interpreter": "baseline-interpreter",
        "trampoline": "trampoline",
        "shared-ic": "shared-ic",
        "baseline-script:self-hosted": "baseline-script",
        "baseline-script:guest-chrome": "baseline-script",
        "baseline-ic": "baseline-ic",
        "regexp": "regexp",
    }

    # For baseline-script we split one owner across two buckets; compute
    # ground totals proportionally by within-class share.
    bl_totals = {"self-hosted": 0, "guest-chrome": 0}
    for pr in per:
        for b in pr["baseline_alive"]:
            sc = "self-hosted" if b["source_class"] == "self-hosted" \
                else "guest-chrome"
            bl_totals[sc] += b["bytes"]
    bl_recon_total = sum(bl_totals.values())
    bl_ground_total = total_by_owner.get("baseline-script", 0)

    def ground_for(cls_name):
        if cls_name.startswith("baseline-script:"):
            sc = cls_name.split(":", 1)[1]
            if bl_recon_total == 0:
                return 0
            return round(bl_ground_total * bl_totals[sc] / bl_recon_total)
        return total_by_owner.get(OWNER_OF[cls_name], 0)

    artifacts = []
    accounted = set()
    for cls_name in [
        "baseline-interpreter", "trampoline", "shared-ic",
        "baseline-script:self-hosted", "baseline-script:guest-chrome",
        "baseline-ic", "regexp",
    ]:
        instances = buckets.get(cls_name, [])
        gt = ground_for(cls_name)
        if gt == 0 and not instances:
            continue
        accounted.add(OWNER_OF[cls_name])
        cs, ash, unq = three_band(instances, gt)
        artifacts.append({
            "name": cls_name,
            "total": cs + ash + unq,
            "currently_shared": cs,
            "achievable_shared": ash,
            "unique": unq,
        })

    ion_total = total_by_owner.get("ion", 0)
    accounted.add("ion")

    unaccounted = set(total_by_owner.keys()) - accounted
    unaccounted.discard("wasm")   # not a JIT class we care about
    unaccounted.discard("other")  # catch-all bucket
    if unaccounted:
        rows = ", ".join(f"{o}={total_by_owner[o]}"
                         for o in sorted(unaccounted))
        die(f"peak snapshot has owner classes with no attribution rule: "
            f"{rows}. Add a bucket in shareability.py.")

    out = {
        "peak_checkpoint": ck["name"],
        "n_procs": n_procs,
        "artifacts": artifacts,
        "ion_total": ion_total,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
