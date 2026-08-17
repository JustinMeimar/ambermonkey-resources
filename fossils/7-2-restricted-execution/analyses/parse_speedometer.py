#!/usr/bin/env python3
"""Parse one Speedometer observation while retaining per-run browser samples."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest, raptor, speedometer3

PREFIX = "parse_speedometer.py"


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    page_cycles = manifest.page_cycles_from(command, PREFIX)
    use_aot_image = manifest.command_flag(command, "JIT_OPTION_useAOTImage")
    aot_only = manifest.command_flag(command, "JIT_OPTION_aotOnly")
    jit_backend_disabled = manifest.command_flag(
        command, "JIT_OPTION_disableJitBackend"
    )
    import re
    ion_disabled = (
        "--setpref javascript.options.ion=false" in command
        or re.search(r"(?:^|\s)JIT_OPTION_ion=false(?=\s|$)", command)
        is not None
    )

    if aot_only and not use_aot_image:
        manifest.fail(PREFIX, f"{variant}: aotOnly requires JIT_OPTION_useAOTImage=true")
    if variant == "interp-only" and not jit_backend_disabled:
        manifest.fail(PREFIX, "interp-only: JIT backend was not disabled")

    if aot_only:
        aot_policy = "aot-only"
    elif use_aot_image:
        aot_policy = "runtime-fallback"
    else:
        aot_policy = "disabled"

    execution = {
        "aot_image": "enabled" if use_aot_image else "disabled",
        "aot_policy": aot_policy,
        "ion": (
            "unavailable"
            if jit_backend_disabled
            else "disabled" if ion_disabled else "enabled"
        ),
        "jit_backend": "disabled" if jit_backend_disabled else "enabled",
    }
    return variant, page_cycles, execution


observation = json.load(sys.stdin)
m = manifest.load(PREFIX)
variant, page_cycles, execution = validate_manifest(m)
r = raptor.load(observation, PREFIX)
suite = raptor.single_suite(r, speedometer3.SUITE_NAME, PREFIX)
metrics = speedometer3.parse(suite, PREFIX)

iteration = observation.get("iteration")
if not isinstance(iteration, int) or iteration < 1:
    manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

sample = {
    "score": metrics["score"],
    "total_ms": metrics["total_ms"],
    "workloads_ms": metrics["workloads_ms"],
}
output = {
    "score": metrics["score"],
    "total_ms": metrics["total_ms"],
    "workloads_ms": metrics["workloads_ms"],
    "runs": {f"run_{iteration:02d}": sample},
    "meta": {
        "variant": variant,
        "commit": m.get("git", {}).get("commit", ""),
        "iterations": m.get("iterations"),
        "page_cycles": page_cycles,
        "execution": execution,
    },
}

json.dump(output, sys.stdout, sort_keys=True)
