#!/usr/bin/env python3
"""Parse an oracle-corpus Raptor observation."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import jetstream3, manifest, speedometer3

PREFIX = "parse_benchmark.py"
WORKLOADS = {
    "jetstream3": jetstream3.parse_observation,
    "speedometer3": speedometer3.parse_observation,
}
POLICIES = {"default", "aot-only"}


def variant_parts(value):
    for policy in sorted(POLICIES, key=len, reverse=True):
        suffix = f"-{policy}"
        if value.endswith(suffix):
            return value[: -len(suffix)], policy
    manifest.fail(PREFIX, f"unexpected variant {value!r}")


def validate_manifest(value):
    variant = value.get("variant")
    command = value.get("command")
    if not isinstance(variant, str):
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    workload, policy = variant_parts(variant)
    if workload not in WORKLOADS:
        manifest.fail(PREFIX, f"{variant}: unexpected workload {workload!r}")

    use_aot_image = manifest.command_flag(command, "JIT_OPTION_useAOTImage")
    aot_only = manifest.command_flag(command, "JIT_OPTION_aotOnly")
    native_regexp_enabled = manifest.command_flag(
        command, "JIT_OPTION_nativeRegExp"
    )
    native_regexp_disabled = (
        re.search(
            r"(?:^|\s)JIT_OPTION_nativeRegExp=false(?=\s|$)", command
        )
        is not None
    )
    ion_disabled = "--setpref javascript.options.ion=false" in command

    if policy == "aot-only":
        if not use_aot_image or not aot_only:
            manifest.fail(PREFIX, f"{variant}: AOT image and aotOnly must be enabled")
        if native_regexp_enabled or not native_regexp_disabled:
            manifest.fail(PREFIX, f"{variant}: native RegExp must be disabled")
        if not ion_disabled:
            manifest.fail(PREFIX, f"{variant}: Ion must be disabled")
    elif use_aot_image or aot_only:
        manifest.fail(PREFIX, f"{variant}: default execution must not enable AOT")

    return variant, workload, policy, manifest.page_cycles_from(command, PREFIX)


def main():
    observation = json.load(sys.stdin)
    run_manifest = manifest.load(PREFIX)
    variant, workload, policy, page_cycles = validate_manifest(run_manifest)
    metrics = WORKLOADS[workload](observation, PREFIX)

    iteration = observation.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

    output = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "workload": workload,
            "policy": policy,
            "commit": run_manifest.get("git", {}).get("commit", ""),
            "iterations": run_manifest.get("iterations"),
            "page_cycles": page_cycles,
        },
    }
    json.dump(output, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
