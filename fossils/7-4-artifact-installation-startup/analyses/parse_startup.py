#!/usr/bin/env python3
"""Parse first-iteration times from the selected JetStream 3 workloads."""

import json
import math
import os
import re
import sys
from urllib.parse import parse_qs

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import jetstream3, manifest, raptor

PREFIX = "parse_startup.py"
EXPECTED_WORKLOADS = frozenset(
    {
        "babylonjs-startup-es5",
        "babylonjs-startup-es6",
        "jsdom-d3-startup",
        "mobx-startup",
        "prismjs-startup-es5",
        "prismjs-startup-es6",
    }
)


def url_parameters(command):
    match = re.search(r"--test-url-params\s+(['\"])(.*?)\1", command)
    if not match:
        manifest.fail(PREFIX, "missing --test-url-params")
    return parse_qs(match.group(2), keep_blank_values=True)


def validate_manifest(record):
    variant = record.get("variant")
    command = record.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    params = url_parameters(command)
    if params.get("tags") != ["startup"]:
        manifest.fail(PREFIX, f"{variant}: expected the JetStream startup tag")
    if params.get("iterationCount") != ["2"]:
        manifest.fail(PREFIX, f"{variant}: iterationCount must be 2")
    if params.get("worstCaseCount") != ["1"]:
        manifest.fail(PREFIX, f"{variant}: worstCaseCount must be 1")

    use_aot = manifest.command_flag(command, "JIT_OPTION_useAOTImage")
    use_aot_ic = manifest.command_flag(command, "JIT_OPTION_useAOTIC")
    use_aot_baseline = manifest.command_flag(command, "JIT_OPTION_useAOTBaseline")
    aot_only = manifest.command_flag(command, "JIT_OPTION_aotOnly")
    native_regex_off = (
        re.search(r"(?:^|\s)JIT_OPTION_nativeRegExp=false(?=\s|$)", command)
        is not None
    )
    headless = "--setenv MOZ_HEADLESS=1" in command
    ion_off = "--setpref javascript.options.ion=false" in command
    wasm_off = "--setpref javascript.options.wasm=false" in command

    if not headless:
        manifest.fail(PREFIX, f"{variant}: headless mode was not enabled")
    if not wasm_off:
        manifest.fail(PREFIX, f"{variant}: WebAssembly was not disabled")

    if variant == "aot-corpus":
        if not (use_aot and aot_only and ion_off and native_regex_off):
            manifest.fail(PREFIX, "aot-corpus: incomplete restricted-execution policy")
    if variant == "aot-corpus-ic":
        if not (
            use_aot_ic
            and not use_aot
            and not use_aot_baseline
            and aot_only
            and ion_off
            and native_regex_off
        ):
            manifest.fail(PREFIX, "aot-corpus-ic: incomplete IC-only policy")
    if variant == "default-no-ion":
        if (
            use_aot
            or use_aot_ic
            or use_aot_baseline
            or aot_only
            or not ion_off
            or not native_regex_off
        ):
            manifest.fail(PREFIX, "default-no-ion: configurations are not matched")

    execution = {
        "aot_image": "enabled" if use_aot or use_aot_ic or use_aot_baseline else "disabled",
        "aot_ic": "enabled" if use_aot or use_aot_ic else "disabled",
        "aot_baseline_functions": (
            "enabled" if use_aot or use_aot_baseline else "disabled"
        ),
        "aot_policy": "aot-only" if aot_only else "disabled",
        "ion": "disabled" if ion_off else "enabled",
        "native_regexp": "disabled" if native_regex_off else "enabled",
        "wasm": "disabled",
    }
    return variant, command, execution


def first_times(suite):
    values = {}
    for subtest in suite.get("subtests") or []:
        name = subtest.get("name", "")
        if not name.endswith("-First"):
            continue
        value = subtest.get("value")
        if not isinstance(value, (int, float)) or value <= 0:
            manifest.fail(PREFIX, f"invalid first-iteration time for {name!r}")
        values[name.removesuffix("-First")] = float(value)

    observed = frozenset(values)
    if observed != EXPECTED_WORKLOADS:
        missing = sorted(EXPECTED_WORKLOADS - observed)
        extra = sorted(observed - EXPECTED_WORKLOADS)
        manifest.fail(PREFIX, f"unexpected First metrics; missing={missing}, extra={extra}")
    return values


observation = json.load(sys.stdin)
record = manifest.load(PREFIX)
variant, command, execution = validate_manifest(record)
suite = raptor.single_suite(raptor.load(observation, PREFIX), jetstream3.SUITE_NAME, PREFIX)
workloads_ms = first_times(suite)
startup_geomean_ms = math.exp(
    math.fsum(math.log(value) for value in workloads_ms.values()) / len(workloads_ms)
)

iteration = observation.get("iteration")
if not isinstance(iteration, int) or iteration < 1:
    manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

sample = {
    "startup_geomean_ms": startup_geomean_ms,
    "workloads_ms": workloads_ms,
}
output = {
    **sample,
    "runs": {f"run_{iteration:02d}": sample},
    "meta": {
        "variant": variant,
        "commit": record.get("git", {}).get("commit", ""),
        "iterations": record.get("iterations"),
        "page_cycles": manifest.page_cycles_from(command, PREFIX),
        "jetstream_internal_iterations": 2,
        "workload_count": len(EXPECTED_WORKLOADS),
        "execution": execution,
    },
}

json.dump(output, sys.stdout, sort_keys=True)
