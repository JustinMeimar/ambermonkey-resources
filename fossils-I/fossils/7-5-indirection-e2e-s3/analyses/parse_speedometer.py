#!/usr/bin/env python3
"""Parse one Speedometer observation while retaining per-run browser samples."""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from benchmarks import manifest, raptor, speedometer3

PREFIX = "parse_speedometer.py"
BASELINE = "default-no-ion"
CANDIDATE = "aot-corpus"
VARIANTS = {BASELINE, CANDIDATE}


def false_flag(command, name):
    pattern = rf"(?:^|\s){re.escape(name)}=false(?=\s|$)"
    return re.search(pattern, command) is not None


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")

    page_cycles = manifest.page_cycles_from(command, PREFIX)
    use_aot_image = manifest.command_flag(command, "JIT_OPTION_useAOTImage")
    aot_only = manifest.command_flag(command, "JIT_OPTION_aotOnly")
    aot_enforce = manifest.command_flag(command, "JIT_OPTION_aotEnforce")
    aot_skip_baseline_fn = manifest.command_flag(
        command, "JIT_OPTION_aotSkipBaselineFn"
    )
    jit_backend_disabled = manifest.command_flag(
        command, "JIT_OPTION_disableJitBackend"
    )
    ion_disabled = (
        "--setpref javascript.options.ion=false" in command
        or re.search(r"(?:^|\s)JIT_OPTION_ion=false(?=\s|$)", command)
        is not None
    )
    native_regexp_enabled = manifest.command_flag(
        command, "JIT_OPTION_nativeRegExp"
    )
    native_regexp_disabled = false_flag(command, "JIT_OPTION_nativeRegExp")

    if aot_only and not use_aot_image:
        manifest.fail(PREFIX, f"{variant}: aotOnly requires JIT_OPTION_useAOTImage=true")
    if not ion_disabled:
        manifest.fail(PREFIX, f"{variant}: Ion must be disabled")
    if native_regexp_enabled or not native_regexp_disabled:
        manifest.fail(PREFIX, f"{variant}: native RegExp must be disabled")
    if jit_backend_disabled:
        manifest.fail(PREFIX, f"{variant}: JIT backend must be enabled")
    if aot_skip_baseline_fn:
        manifest.fail(PREFIX, f"{variant}: AOT Baseline functions must be enabled")

    if variant == CANDIDATE:
        if not use_aot_image or not aot_only:
            manifest.fail(PREFIX, f"{variant}: AOT image and aotOnly must be enabled")
        if aot_enforce:
            manifest.fail(PREFIX, f"{variant}: aotEnforce must not be enabled")
    elif use_aot_image or aot_only or aot_enforce:
        manifest.fail(PREFIX, f"{variant}: Baseline comparison must not enable AOT")

    if aot_only:
        aot_policy = "aot-only"
    elif use_aot_image:
        aot_policy = "runtime-fallback"
    else:
        aot_policy = "disabled"

    execution = {
        "aot_image": "enabled" if use_aot_image else "disabled",
        "aot_policy": aot_policy,
        "aot_baseline_functions": "disabled" if aot_skip_baseline_fn else "enabled",
        "native_regexp": "disabled" if native_regexp_disabled else "enabled",
        "ion": (
            "unavailable"
            if jit_backend_disabled
            else "disabled" if ion_disabled else "enabled"
        ),
        "jit_backend": "disabled" if jit_backend_disabled else "enabled",
    }
    return variant, page_cycles, execution


def main():
    observation = json.load(sys.stdin)
    m = manifest.load(PREFIX, run_dir=sys.argv[2], observation=observation)
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


if __name__ == "__main__":
    main()
