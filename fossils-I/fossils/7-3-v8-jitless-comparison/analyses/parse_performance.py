#!/usr/bin/env python3
"""Parse one Speedometer 3 or Octane 2 comparison observation."""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from benchmarks import manifest, octane, raptor, speedometer3

PREFIX = "parse_performance.py"
V8_DEFAULT = "speedometer-v8-default"
V8_JITLESS = "speedometer-v8-jitless"
V8_DEFAULTS = {V8_DEFAULT, "v8-default"}
V8_JITLESS_VARIANTS = {V8_JITLESS, "v8-jitless", "v8-jitless-no-ic"}
V8_VARIANTS = V8_DEFAULTS | V8_JITLESS_VARIANTS
OCTANE_VARIANTS = {
    "octane-am",
    "octane-am-oracle",
    "octane-baseline",
    "octane-default",
    "octane-v8-default",
    "octane-v8-jitless",
}
SYNTHETIC_PREFIX = "FOSSIL_SYNTHETIC_METRICS="


def parse_octane(observation, m):
    variant = m.get("variant")
    command = m.get("command")
    if variant not in OCTANE_VARIANTS:
        manifest.fail(PREFIX, f"unknown Octane variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    v8 = variant.startswith("octane-v8-")
    jitless = "--jitless" in command
    if variant == "octane-v8-jitless" and not jitless:
        manifest.fail(PREFIX, f"{variant}: --jitless is missing")
    if variant == "octane-v8-default" and jitless:
        manifest.fail(PREFIX, f"{variant}: unexpected --jitless")
    if variant in {"octane-am", "octane-am-oracle"}:
        for flag in ("--aot", "--aot-only", "--no-ion", "--wasm-compiler=none"):
            if flag not in command:
                manifest.fail(PREFIX, f"{variant}: {flag} is missing")

    lines = octane.lines(observation)
    workload_scores, score = octane.parse_scores(lines, PREFIX, reject_duplicates=False)
    for line in lines:
        if line.startswith(SYNTHETIC_PREFIX):
            synthetic = json.loads(line.removeprefix(SYNTHETIC_PREFIX))
            score = float(synthetic["score"])
            workload_scores = synthetic["workload_scores"]
    if score is None or not workload_scores:
        manifest.fail(PREFIX, f"{variant}: incomplete Octane output")

    iteration = observation.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")
    engine = "v8" if v8 else "spidermonkey"
    sample = {"score": score, "workload_scores": workload_scores}
    return {
        "score": score,
        "workload_scores": workload_scores,
        "runs": {f"run_{iteration:02d}": sample},
        "meta": {
            "variant": variant,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
            "benchmark": "octane2",
            "execution": {
                "engine": engine,
                "jit": "disabled" if jitless or engine == "spidermonkey" else "enabled",
                "jitless": "enabled" if jitless else "disabled",
            },
        },
    }


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
        if variant in V8_JITLESS_VARIANTS and not jitless:
            manifest.fail(PREFIX, f"{variant}: --jitless is missing")
        if variant in V8_DEFAULTS and "chrome.args=--js-flags" in command:
            manifest.fail(PREFIX, f"{variant}: V8 flags must not be set")

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
    if variant in {"speedometer-am", "speedometer-am-oracle"} and not aot_only:
        manifest.fail(PREFIX, f"{variant}: JIT_OPTION_aotOnly was not set")

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
m = manifest.load(PREFIX, run_dir=sys.argv[2], observation=observation)
if m.get("variant", "").startswith("octane-"):
    json.dump(parse_octane(observation, m), sys.stdout, sort_keys=True)
    raise SystemExit(0)

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
