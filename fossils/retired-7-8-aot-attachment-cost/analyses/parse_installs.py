#!/usr/bin/env python3
"""Per-artifact aggregate of AOT install vs runtime compile from a
run_block.py observation.

Emits one section per artifact class (interpreter, baseline scripts, IC
stubs) with mean per-call time in each cell, mean per-process call count,
and AOT-image byte contribution per process. The figure script folds
these into a single table."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest


PREFIX = "aot_attachment_cost"
ARTIFACTS = (
    # (row-key, install-phase, compile-phase, image-counter)
    ("interpreter", "interpreter_install", "interpreter_generate",
     "interpreter_image_bytes"),
    ("baseline_scripts", "baseline_install", "baseline_compile",
     "baseline_image_bytes"),
    ("ic_stubs", "ic_install", "ic_compile", "ic_image_bytes"),
)


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


def cell_totals(cell):
    """Sum phases and counters across content-process records for one cell.

    Returns (n_procs, {phase: (calls, total_ns)}, {counter: bytes})."""
    records = cell.get("timing_records", [])
    if not records:
        manifest.fail(PREFIX, "cell has no content-process records")
    n = len(records)
    phases = {}
    counters = {}
    for record in records:
        for name, info in record.get("phases", {}).items():
            calls_sum, ns_sum = phases.get(name, (0, 0))
            phases[name] = (calls_sum + info["calls"],
                            ns_sum + info["total_ns"])
        for name, value in record.get("counters", {}).items():
            counters[name] = counters.get(name, 0) + value
    return n, phases, counters


def per_call_us(phases, phase):
    calls, ns = phases.get(phase, (0, 0))
    if calls == 0:
        return 0.0
    return ns / calls / 1000.0


def per_proc(value, n):
    return value / n if n else 0.0


def main():
    record_manifest = manifest.load(PREFIX)
    if record_manifest.get("variant") != "blocked":
        manifest.fail(PREFIX, "expected the blocked variant")

    observation = json.load(sys.stdin)
    payload = driver_payload(observation)
    cells = payload["cells"]
    expected = {"runtime", "aot"}
    if set(cells) != expected:
        manifest.fail(PREFIX, f"unexpected cells: {sorted(cells)}")

    n_runtime, runtime_phases, _ = cell_totals(cells["runtime"])
    n_aot, aot_phases, aot_counters = cell_totals(cells["aot"])

    artifacts = {}
    for key, install_phase, compile_phase, image_counter in ARTIFACTS:
        install_calls, _ = aot_phases.get(install_phase, (0, 0))
        compile_calls, _ = runtime_phases.get(compile_phase, (0, 0))
        artifacts[key] = {
            "install_us_per_call": per_call_us(aot_phases, install_phase),
            "compile_us_per_call": per_call_us(runtime_phases, compile_phase),
            "installs_per_proc": per_proc(install_calls, n_aot),
            "compiles_per_proc": per_proc(compile_calls, n_runtime),
            "image_bytes_per_proc": per_proc(aot_counters.get(image_counter, 0),
                                             n_aot),
        }

    metrics = {
        "artifacts": artifacts,
        "content_processes": {"runtime": n_runtime, "aot": n_aot},
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
