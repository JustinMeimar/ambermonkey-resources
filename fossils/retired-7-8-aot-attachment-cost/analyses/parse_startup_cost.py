#!/usr/bin/env python3
"""Aggregate cpstartup timing and per-phase counters from a run_block.py observation."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest


PREFIX = "aot_attachment_cost"
PHASES = (
    "image_compatibility",
    "interpreter_attach",
    "rit_initialization",
    "ic_corpus_attach",
    "baseline_function_lookup",
    "baseline_function_reconstruct",
    "ic_image_lookup",
    "ic_private_attach",
    "runtime_baseline_compile",
    "runtime_ic_compile",
)
AOT_PHASES = PHASES[:-2]
COMPILE_PHASES = PHASES[-2:]


def driver_payload(observation):
    stdout = observation.get("stdout", [])
    lines = stdout if isinstance(stdout, list) else stdout.splitlines()
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "cells" in payload:
            return payload
    manifest.fail(PREFIX, "run_block.py payload not found in stdout")


def cpstartup_value(perfherder):
    suites = perfherder.get("suites", [])
    suite = next((item for item in suites if item.get("name") == "cpstartup"), None)
    if suite is None:
        manifest.fail(PREFIX, "cpstartup suite not found in PERFHERDER_DATA")
    value = suite.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    subtest = next(
        (item for item in suite.get("subtests", []) if item.get("name") == "cpstartup"),
        None,
    )
    if subtest and isinstance(subtest.get("value"), (int, float)):
        return float(subtest["value"])
    manifest.fail(PREFIX, "cpstartup value not found in PERFHERDER_DATA")


def aggregate_timing(cell):
    records = [
        record
        for record in cell.get("timing_records", [])
        if record.get("process_type") == "content"
    ]
    if not records:
        manifest.fail(PREFIX, "timed cell contains no content-process records")
    count = len(records)
    phases = {
        phase: sum(record["phases"][phase]["total_ns"] for record in records)
        / count
        / 1_000_000
        for phase in PHASES
    }
    counters = {}
    for record in records:
        for key, value in record.get("counters", {}).items():
            counters[key] = counters.get(key, 0) + value
    counters = {key: value / count for key, value in counters.items()}
    calls = {
        phase: sum(record["phases"][phase]["calls"] for record in records) / count
        for phase in PHASES
    }
    return count, phases, calls, counters


def main():
    record_manifest = manifest.load(PREFIX)
    if record_manifest.get("variant") != "blocked":
        manifest.fail(PREFIX, "expected the blocked variant")
    observation = json.load(sys.stdin)
    payload = driver_payload(observation)
    cells = payload["cells"]
    expected = {"runtime_clean", "aot_clean", "runtime_timed", "aot_timed"}
    if set(cells) != expected:
        manifest.fail(PREFIX, f"unexpected cells: {sorted(cells)}")

    startup = {
        name: cpstartup_value(cell["perfherder"])
        for name, cell in cells.items()
    }
    runtime_count, runtime_phases, runtime_calls, runtime_counters = aggregate_timing(
        cells["runtime_timed"]
    )
    aot_count, aot_phases, aot_calls, aot_counters = aggregate_timing(
        cells["aot_timed"]
    )

    aot_added = sum(aot_phases[phase] for phase in AOT_PHASES)
    runtime_compile = sum(runtime_phases[phase] for phase in COMPILE_PHASES)
    aot_compile = sum(aot_phases[phase] for phase in COMPILE_PHASES)
    metrics = {
        "startup_ms": startup,
        "startup_effect_ms": startup["aot_clean"] - startup["runtime_clean"],
        "startup_effect_ratio": startup["aot_clean"] / startup["runtime_clean"],
        "timing_overhead_ms": {
            "runtime": startup["runtime_timed"] - startup["runtime_clean"],
            "aot": startup["aot_timed"] - startup["aot_clean"],
        },
        "phases_ms_per_process": {
            "runtime": runtime_phases,
            "aot": aot_phases,
        },
        "phase_calls_per_process": {
            "runtime": runtime_calls,
            "aot": aot_calls,
        },
        "counters_per_process": {
            "runtime": runtime_counters,
            "aot": aot_counters,
        },
        "attribution_ms_per_process": {
            "aot_work_added": aot_added,
            "runtime_compilation": runtime_compile,
            "aot_residual_compilation": aot_compile,
            "compilation_saved": runtime_compile - aot_compile,
            "net_direct_balance": aot_added - (runtime_compile - aot_compile),
        },
        "content_processes": {
            "runtime": runtime_count,
            "aot": aot_count,
        },
        "meta": {
            "seed": payload["seed"],
            "order": ",".join(payload["order"]),
            "browser_sha256": payload["browser"]["sha256"],
            "firefox_commit": payload["browser"]["firefox_commit"],
            "iterations": record_manifest.get("iterations", 0),
        },
    }
    json.dump(metrics, sys.stdout)


if __name__ == "__main__":
    main()
