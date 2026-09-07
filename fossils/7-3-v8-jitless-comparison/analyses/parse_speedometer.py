#!/usr/bin/env python3
"""Parse one Speedometer 3 observation for the V8-JITless comparison fossil."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest, raptor, speedometer3

PREFIX = "parse_speedometer.py"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"
V8_JITLESS_NO_IC = "v8-jitless-no-ic"
V8_VARIANTS = {V8_DEFAULT, V8_JITLESS, V8_JITLESS_NO_IC}


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    page_cycles = manifest.page_cycles_from(command, PREFIX)
    if variant in V8_VARIANTS:
        if not manifest.has_option(command, "--app", "chrome"):
            manifest.fail(PREFIX, f"{variant}: Raptor app is not chrome")
        if "run-chromium-nixos.sh" not in command:
            manifest.fail(PREFIX, f"{variant}: non-PGO Chromium launcher is missing")
        if "run-chromedriver-nixos.sh" not in command:
            manifest.fail(PREFIX, f"{variant}: NixOS ChromeDriver launcher is missing")
        if "chrome.args=--headless=new" not in command:
            manifest.fail(PREFIX, f"{variant}: Chromium headless flag is missing")

        jitless = "--jitless" in command
        no_ic = "--no-use-ic" in command
        if variant == V8_JITLESS and not jitless:
            manifest.fail(PREFIX, "v8-jitless: --jitless is missing")
        if variant == V8_JITLESS_NO_IC and (not jitless or not no_ic):
            manifest.fail(
                PREFIX,
                "v8-jitless-no-ic: --jitless and --no-use-ic are required",
            )
        if variant == V8_DEFAULT and "chrome.args=--js-flags" in command:
            manifest.fail(PREFIX, "v8-default: V8 flags must not be set")

        return variant, page_cycles, "chrome", {
            "engine": "v8",
            "jit": "disabled" if jitless else "enabled",
            "jitless": "enabled" if jitless else "disabled",
            "inline_caches": "disabled" if no_ic else "enabled",
            "pgo": "disabled",
        }

    use_aot_image = manifest.command_flag(command, "JIT_OPTION_useAOTImage")
    aot_only = manifest.command_flag(command, "JIT_OPTION_aotOnly")
    jit_backend_disabled = manifest.command_flag(
        command, "JIT_OPTION_disableJitBackend"
    )
    ion_disabled = (
        "--setpref javascript.options.ion=false" in command
        or re.search(r"(?:^|\s)JIT_OPTION_ion=false(?=\s|$)", command) is not None
    )

    if aot_only and not use_aot_image:
        manifest.fail(PREFIX, f"{variant}: aotOnly requires JIT_OPTION_useAOTImage=true")
    if variant == "interp-only" and not jit_backend_disabled:
        manifest.fail(PREFIX, "interp-only: JIT backend was not disabled")
    if variant == "aot-corpus" and not aot_only:
        manifest.fail(PREFIX, "aot-corpus: JIT_OPTION_aotOnly was not set")

    if aot_only:
        aot_policy = "aot-only"
    elif use_aot_image:
        aot_policy = "runtime-fallback"
    else:
        aot_policy = "disabled"

    execution = {
        "engine": "spidermonkey",
        "aot_image": "enabled" if use_aot_image else "disabled",
        "aot_policy": aot_policy,
        "ion": (
            "unavailable"
            if jit_backend_disabled
            else "disabled" if ion_disabled else "enabled"
        ),
        "jit_backend": "disabled" if jit_backend_disabled else "enabled",
    }
    return variant, page_cycles, "firefox", execution


observation = json.load(sys.stdin)
m = manifest.load(PREFIX)
variant, page_cycles, expected_app, execution = validate_manifest(m)
r = raptor.load(observation, PREFIX)
application = r.get("application") or {}
if application.get("name") != expected_app:
    manifest.fail(
        PREFIX,
        f"{variant}: expected application {expected_app!r}, "
        f"found {application.get('name')!r}",
    )
if not isinstance(application.get("version"), str) or not application["version"]:
    manifest.fail(PREFIX, f"{variant}: application version is missing")
suite = raptor.single_suite(r, speedometer3.SUITE_NAME, PREFIX)
metrics = speedometer3.parse(suite, PREFIX)

iteration = observation.get("iteration")
if not isinstance(iteration, int) or iteration < 1:
    manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

sample = {
    "score": metrics["score"],
    "total_ms": metrics["total_ms"],
}
output = {
    "score": metrics["score"],
    "total_ms": metrics["total_ms"],
    "runs": {f"run_{iteration:02d}": sample},
    "meta": {
        "variant": variant,
        "commit": m.get("git", {}).get("commit", ""),
        "iterations": m.get("iterations"),
        "page_cycles": page_cycles,
        "application": application,
        "execution": execution,
    },
}

json.dump(output, sys.stdout, sort_keys=True)
