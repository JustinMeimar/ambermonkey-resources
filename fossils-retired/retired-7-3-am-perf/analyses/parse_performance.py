#!/usr/bin/env python3
"""Reduce one held-out browser run while retaining independent samples."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest, raptor, speedometer3, jetstream3

PREFIX = "parse_performance"

WORKLOADS = ("speedometer3", "jetstream3")
POLICIES = ("interp-only", "am-strict", "default")
VARIANTS = {
    f"{workload}-{policy}": (workload, policy)
    for workload in WORKLOADS
    for policy in POLICIES
}


def validate_manifest(m):
    variant = m.get("variant")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    workload, policy = VARIANTS[variant]
    command = m.get("command", "")

    if not manifest.has_option(command, "--browser-cycles", "1"):
        manifest.fail(PREFIX, f"{variant}: expected one browser cycle")
    if not manifest.has_option(command, "--page-cycles", "1"):
        manifest.fail(PREFIX, f"{variant}: expected one page cycle")
    if not re.search(rf"(?:^|\s)-t\s+{workload}(?:\s|$)", command):
        manifest.fail(PREFIX, f"{variant}: command does not run {workload}")

    for pref in (
        "javascript.options.baselinejit=true",
        "javascript.options.native_regexp=false",
        "javascript.options.wasm=false",
    ):
        if not manifest.has_option(command, "--setpref", pref):
            manifest.fail(PREFIX, f"{variant}: missing matched control {pref}")

    ion_on = policy == "default"
    ion_pref = f"javascript.options.ion={'true' if ion_on else 'false'}"
    if not manifest.has_option(command, "--setpref", ion_pref):
        manifest.fail(PREFIX, f"{variant}: missing {ion_pref}")

    expected_env = {
        "JIT_OPTION_disableJitBackend=true": policy == "interp-only",
        "JIT_OPTION_useAOTImage=true": policy == "am-strict",
        "JIT_OPTION_aotOnly=true": policy == "am-strict",
    }
    for setting, should_exist in expected_env.items():
        exists = manifest.has_option(command, "--setenv", setting)
        if exists != should_exist:
            state = "missing" if should_exist else "unexpected"
            manifest.fail(PREFIX, f"{variant}: {state} --setenv {setting}")

    uses_aot_build = "build-browser-release-aot" in command
    uses_aot_mozconfig = "browser-release-aot.mozconfig" in command
    should_use_aot_build = policy == "am-strict"
    if uses_aot_build != should_use_aot_build:
        build = "AOT release" if should_use_aot_build else "ordinary release"
        manifest.fail(PREFIX, f"{variant}: expected the {build} browser binary")
    if uses_aot_mozconfig != should_use_aot_build:
        config = "AOT release" if should_use_aot_build else "ordinary release"
        manifest.fail(PREFIX, f"{variant}: expected the {config} mozconfig")

    return variant, workload, policy


def parse_speedometer_local(suite):
    """9-3 emits the workloads dict under key `workloads` (not `workloads_ms`)."""
    m = speedometer3.parse(suite, PREFIX)
    return {
        "score": m["score"],
        "total_ms": m["total_ms"],
        "workloads": m["workloads_ms"],
    }


def parse_jetstream_local(suite):
    """9-3 emits per-subtest geometric scores under key `subtests`."""
    overall = jetstream3.parse_overall(suite, PREFIX)
    geometric = jetstream3.parse_geometric(suite, PREFIX)
    if not geometric:
        manifest.fail(PREFIX, "JetStream suite contains no positive -Geometric subtests")
    return {
        "score": overall,
        "subtests": geometric,
        "n_subtests": len(geometric),
    }


def main():
    observation = json.load(sys.stdin)
    m = manifest.load(PREFIX)
    variant, workload, policy = validate_manifest(m)
    r = raptor.load(observation, PREFIX)
    if workload == "speedometer3":
        suite = raptor.single_suite(r, speedometer3.SUITE_NAME, PREFIX)
        metrics = parse_speedometer_local(suite)
    else:
        suite = raptor.single_suite(r, jetstream3.SUITE_NAME, PREFIX)
        metrics = parse_jetstream_local(suite)

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
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
            "browser_cycles": 1,
            "page_cycles": 1,
            "ion": policy == "default",
            "native_regexp": False,
            "wasm": False,
        },
    }
    json.dump(output, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
