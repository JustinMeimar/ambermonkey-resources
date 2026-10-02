#!/usr/bin/env python3
"""JIT allocation analysis over a memory summary observation."""

import collections
import json
import sys

OWNER_GROUPS = {
    "fixed-baseline": ("baseline-interpreter", "shared-ic"),
    "engine-owned": ("baseline-interpreter", "trampoline", "shared-ic"),
}


def load_summary():
    observation = json.load(sys.stdin)
    if "observations" in observation:
        observations = observation["observations"]
        if len(observations) != 1:
            raise ValueError("expected one Fossil observation")
        observation = observations[0]
    if observation.get("exit_code", 0) != 0:
        return observation, None
    stdout = observation.get("stdout")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    if not isinstance(stdout, str) or not stdout.strip():
        return observation, None
    return observation, json.loads(stdout.strip())


def total_smaps(procs):
    total = collections.Counter()
    for proc in procs:
        total.update(proc["smaps"])
    return dict(total)


def crosscheck(reporter, mapped):
    if reporter is None:
        return {"available": 0}

    low = reporter["code_used_bytes"] + reporter["code_unused_bytes"]
    high = low + reporter["code_sundries_bytes"]
    return {
        "available": 1,
        "reported_low_bytes": low,
        "reported_high_bytes": high,
        "measured_bytes": mapped,
        "within_bracket": int(low <= mapped <= high),
        "excess_bytes": max(0, mapped - high) or min(0, mapped - low),
        "missing_snapshot_pids": reporter["missing_snapshot_pids"],
    }


def checkpoint_row(checkpoint):
    procs = checkpoint["procs"]
    owners = collections.Counter()
    kinds = collections.Counter()
    for proc in procs:
        owners.update(proc["live_by_owner"])
        kinds[proc["kind"]] += 1

    pool_used = sum(proc["pool_used_bytes"] for proc in procs)
    pool_unused = sum(proc["pool_unused_bytes"] for proc in procs)
    mapped = sum(proc["mmap_bytes"] for proc in procs)
    code_bytes = sum(owners.values())
    return {
        "index": checkpoint["index"],
        "name": checkpoint["name"],
        "processes": dict(kinds),
        "reporter": crosscheck(checkpoint["reporter"], mapped),
        "code_bytes": code_bytes,
        "mmap_bytes": mapped,
        "pool_used_bytes": pool_used,
        "pool_unused_bytes": pool_unused,
        "smaps": total_smaps(procs),
        "by_owner": dict(owners),
        "owner_groups": {
            name: {
                "owners": list(group),
                "bytes": sum(owners[owner] for owner in group),
                "share_of_code": (
                    sum(owners[owner] for owner in group) / code_bytes
                    if code_bytes else 0
                ),
            }
            for name, group in OWNER_GROUPS.items()
        },
    }


def main():
    observation, summary = load_summary()
    if summary is None:
        print(json.dumps({
            "observation": {
                "valid": 0,
                "exit_code": observation.get("exit_code", -1),
            }
        }, indent=2))
        return

    checkpoints = {
        checkpoint["name"]: checkpoint_row(checkpoint)
        for checkpoint in summary["checkpoints"]
    }
    peak = max(checkpoints.values(), key=lambda c: c["code_bytes"])
    checked = [c["reporter"] for c in checkpoints.values()
               if c["reporter"]["available"]]
    result = {
        "observation": {
            "valid": 1,
            "exit_code": observation.get("exit_code", 0),
        },
        "processes_ever": summary["n_processes"],
        "parent_processes_ever": summary["n_parent"],
        "peak_checkpoint": peak["name"],
        "crosscheck": {
            "checkpoints_checked": len(checked),
            "checkpoints_without_report": summary["checkpoints_without_report"],
            "checkpoints_outside_bracket": [
                c["name"] for name, c in checkpoints.items()
                if c["reporter"]["available"] and not c["reporter"]["within_bracket"]
            ],
            "missing_snapshot_pids": sorted({
                pid for c in checked for pid in c["missing_snapshot_pids"]
            }),
        },
        "checkpoints": checkpoints,
    }
    if "perfherder" in summary:
        result["perfherder"] = summary["perfherder"]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
