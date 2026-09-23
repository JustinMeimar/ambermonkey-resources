#!/usr/bin/env python3
"""Per-case loop-adjusted ns/op for each profile, plus V8/SM speedup ratios.

Reads one observation whose stdout is the seed JSON adjacent to fossil.toml
and produces a flat map keyed by case. Cases are sorted by descending
V8_sparkplug / SM_cacheir so the figure lays out the strongest SM wins first.
"""

import json
import math
import statistics
import sys


PREFIX = "op_speedup.py"


def die(message):
    print(f"{PREFIX}: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def observation_seed(record):
    observations = record.get("observations") or [record]
    if len(observations) != 1:
        die(f"expected exactly one observation, got {len(observations)}")
    obs = observations[0]
    if int(obs.get("exit_code", 0)) != 0:
        die(f"seed observation exited with status {obs.get('exit_code')}")
    output = obs.get("stdout")
    if isinstance(output, list):
        output = "\n".join(output)
    if not isinstance(output, str) or not output.strip():
        die("seed observation produced no stdout")
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        die(f"seed observation stdout is not valid JSON: {exc}")


def profile_stats(case, profile):
    entry = case["profiles"].get(profile)
    if entry is None:
        die(f"case {case['case']!r} missing profile {profile!r}")
    samples = entry.get("samplesNsPerIteration") or []
    if not samples:
        die(f"case {case['case']!r} profile {profile!r} has no samples")
    return {
        "median": statistics.median(samples),
        "mean": statistics.fmean(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "n": len(samples),
    }


def loop_adjusted(case_stats, loop_stats, ops_per_iteration):
    """Return ns/op after subtracting the profile's loop-control median."""
    return (case_stats["median"] - loop_stats["median"]) / ops_per_iteration


def main():
    record = json.load(sys.stdin)
    seed = observation_seed(record)

    cases = seed.get("cases") or []
    if not cases:
        die("seed contains no cases")

    loop_name = seed.get("loopControlCase", "loop_control")
    loop_case = next((c for c in cases if c["case"] == loop_name), None)
    if loop_case is None:
        die(f"seed missing loop-control case {loop_name!r}")

    profiles = sorted(loop_case["profiles"].keys())
    required = {"sm-cacheir", "sm-no-cacheir", "v8-sparkplug"}
    missing = required - set(profiles)
    if missing:
        die(f"seed missing required profiles: {sorted(missing)}")

    loop_stats = {p: profile_stats(loop_case, p) for p in profiles}

    ordered = []
    per_case = {}
    for case in cases:
        name = case["case"]
        if name == loop_name:
            continue
        ops = case["opsPerIteration"]
        case_stats = {p: profile_stats(case, p) for p in profiles}
        adj = {p: loop_adjusted(case_stats[p], loop_stats[p], ops) for p in profiles}
        sm_on = adj["sm-cacheir"]
        sm_off = adj["sm-no-cacheir"]
        v8_sp = adj["v8-sparkplug"]

        if sm_on <= 0:
            die(f"case {name!r} has non-positive loop-adjusted SM cost {sm_on}")

        entry = {
            "family": case.get("family", ""),
            "cache_kind": case.get("cacheKind") or "",
            "ops_per_iteration": ops,
            "sm_cacheir_ns_per_op": sm_on,
            "sm_no_cacheir_ns_per_op": sm_off,
            "v8_sparkplug_ns_per_op": v8_sp,
            "v8_over_sm": v8_sp / sm_on,
            "log2_v8_over_sm": math.log2(v8_sp / sm_on) if v8_sp > 0 else 0.0,
            "sm_off_over_on": sm_off / sm_on if sm_on > 0 else 0.0,
        }
        # optional: v8 jitless
        if "v8-jitless" in profiles:
            jl = loop_adjusted(case_stats["v8-jitless"], loop_stats["v8-jitless"], ops)
            entry["v8_jitless_ns_per_op"] = jl
            entry["v8_jitless_over_sm"] = jl / sm_on

        per_case[name] = entry
        ordered.append((name, entry["v8_over_sm"]))

    ordered.sort(key=lambda item: item[1], reverse=True)

    output = {
        "cases": per_case,
        "case_order": ",".join(name for name, _ in ordered),
        "meta": {
            "platform": (
                f"{seed.get('platform', {}).get('arch', '?')}/"
                f"{seed.get('platform', {}).get('platform', '?')}"
            ),
            "generated_at": seed.get("generatedAt", ""),
            "loop_control_case": loop_name,
            "profiles": profiles,
        },
    }
    json.dump(output, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
