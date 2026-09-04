#!/usr/bin/env python3
"""Parse perf NDJSON for every indirection microbenchmark in one observation."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "parse_cycles"
VARIANTS = ("baseline-jit", "am-rit", "am-rit-nl", "am-rit-nl-vm")
ITER_COUNTS = {
    "interrupt-check": 250_000_000,
    "stack-check": 100_000_000,
    "prebarrier": 200_000_000,
    "vm-call": 100_000_000,
    "abi-call": 50_000_000,
}
BENCHES = tuple(ITER_COUNTS)
REQUIRED_EVENTS = ("cycles:u", "instructions:u", "ref-cycles:u")
BENCHMARK_MARKER = "# benchmark="
MIN_RUNNING = 99.5
BEST_OBSERVATIONS = 30


def split_benchmark_output(text):
    groups = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(BENCHMARK_MARKER):
            current = stripped.removeprefix(BENCHMARK_MARKER)
            if current in groups:
                manifest.fail(PREFIX, f"duplicate benchmark marker {current!r}")
            groups[current] = []
        elif current is not None:
            groups[current].append(line)
    return {bench: "\n".join(lines) for bench, lines in groups.items()}


def parse_perf_ndjson(text):
    events = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = obj.get("event")
        val = obj.get("counter-value")
        if event is None or val is None:
            continue
        try:
            value = float(val)
        except (TypeError, ValueError):
            manifest.fail(PREFIX, f"non-numeric counter for {event}: {val!r}")
        try:
            pcnt_running = float(obj.get("pcnt-running", 0.0))
        except (TypeError, ValueError):
            pcnt_running = 0.0
        events[event] = {"value": value, "pcnt_running": pcnt_running}
    return events


def metrics_for(bench, text):
    events = parse_perf_ndjson(text)
    for req in REQUIRED_EVENTS:
        if req not in events:
            manifest.fail(PREFIX, f"{bench}: missing event {req}")
        if events[req]["pcnt_running"] < MIN_RUNNING:
            manifest.fail(
                PREFIX,
                f"{bench}: {req} multiplexed at "
                f"{events[req]['pcnt_running']:.2f}% (< {MIN_RUNNING}%)",
            )

    cycles = events["cycles:u"]["value"]
    insns = events["instructions:u"]["value"]
    return {
        "cycles_user": cycles,
        "instructions_user": insns,
        "ref_cycles_user": events["ref-cycles:u"]["value"],
        "cycles_per_iter": cycles / ITER_COUNTS[bench],
        "insns_per_iter": insns / ITER_COUNTS[bench],
        "ipc": (insns / cycles) if cycles else 0.0,
    }


def observation_text(obs):
    stdout = obs.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not isinstance(text, str) or not text.strip():
        manifest.fail(PREFIX, "empty stdout; perf produced no JSON")
    return text


def benchmark_groups(obs):
    groups = split_benchmark_output(observation_text(obs))
    missing = [bench for bench in BENCHES if bench not in groups]
    extras = sorted(set(groups) - set(BENCHES))
    if missing or extras:
        manifest.fail(
            PREFIX,
            f"benchmark mismatch: missing={missing!r}, unexpected={extras!r}",
        )
    return groups


def excluded_iterations_by_benchmark():
    run_dir = os.environ.get("FOSSIL_RUN_DIR")
    if not run_dir:
        manifest.fail(PREFIX, "FOSSIL_RUN_DIR is required for trimmed analysis")
    with open(os.path.join(run_dir, "results.json")) as results_file:
        observations = json.load(results_file).get("observations", [])
    if len(observations) < BEST_OBSERVATIONS:
        manifest.fail(
            PREFIX,
            f"need at least {BEST_OBSERVATIONS} observations for selection",
        )

    ranked = {bench: [] for bench in BENCHES}
    for observation in observations:
        iteration = observation.get("iteration")
        if not isinstance(iteration, int):
            manifest.fail(PREFIX, "observation is missing an integer iteration")
        groups = benchmark_groups(observation)
        for bench in BENCHES:
            cycles = metrics_for(bench, groups[bench])["cycles_user"]
            ranked[bench].append((cycles, iteration))

    excluded = {}
    for bench, observations_for_bench in ranked.items():
        observations_for_bench.sort()
        excluded[bench] = {
            iteration
            for _, iteration in observations_for_bench[BEST_OBSERVATIONS:]
        }
    return excluded


def main():
    obs = json.load(sys.stdin)
    m = manifest.load(PREFIX)
    variant = m.get("variant", "")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unrecognized variant {variant!r}")

    groups = benchmark_groups(obs)
    excluded = excluded_iterations_by_benchmark()
    benchmarks = {
        bench: metrics_for(bench, groups[bench])
        for bench in BENCHES
        if obs.get("iteration") not in excluded[bench]
    }

    out = {
        "benchmarks": benchmarks,
        "meta": {
            "variant": variant,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
            "retained_observations_per_benchmark": BEST_OBSERVATIONS,
            "selection": "30 lowest-cycle observations retained independently per benchmark",
        },
    }

    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
