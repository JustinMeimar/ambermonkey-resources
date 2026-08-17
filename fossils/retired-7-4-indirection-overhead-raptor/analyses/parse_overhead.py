#!/usr/bin/env python3
"""Parse a JetStream/Speedometer run to score the AOT-oracle vs baseline overhead."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest, raptor, speedometer3, jetstream3

PREFIX = "parse_overhead"

VARIANTS = {
    "jetstream3-baseline":     ("jetstream3",   False),
    "jetstream3-aot-oracle":   ("jetstream3",   True),
    "speedometer3-baseline":   ("speedometer3", False),
    "speedometer3-aot-oracle": ("speedometer3", True),
}


def validate(m):
    variant = m.get("variant")
    if variant not in VARIANTS:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    workload, aot_only = VARIANTS[variant]
    cmd = m.get("command", "")
    for pref in (
        "javascript.options.ion=false",
        "javascript.options.native_regexp=false",
        "javascript.options.wasm=false",
    ):
        if pref not in cmd:
            manifest.fail(PREFIX, f"{variant}: pref {pref} not set")
    if aot_only:
        if "JIT_OPTION_aotOnly=true" not in cmd:
            manifest.fail(PREFIX, f"{variant}: JIT_OPTION_aotOnly=true not set")
    elif "JIT_OPTION_aotOnly=true" in cmd:
        manifest.fail(PREFIX, f"{variant}: baseline variant must not set JIT_OPTION_aotOnly")
    expected_cycles = 3 if workload == "speedometer3" else 1
    if not re.search(rf"--page-cycles(?:=|\s+){expected_cycles}(?:\s|$)", cmd):
        manifest.fail(PREFIX, f"{variant}: expected --page-cycles {expected_cycles}")
    return variant, workload, aot_only


def main():
    obs = json.load(sys.stdin)
    m = manifest.load(PREFIX)
    variant, workload, aot_only = validate(m)

    r = raptor.load(obs, PREFIX)

    if workload == "jetstream3":
        suite = raptor.single_suite(r, jetstream3.SUITE_NAME, PREFIX)
        overall = jetstream3.parse_overall(suite, PREFIX)
        startup = jetstream3.parse_startup(suite, PREFIX)
        metrics = {
            "score": overall,
            "startup_score": startup["startup_score"],
            "startup_geomean_ms": startup["startup_geomean_ms"],
            "n_subtests": startup["n_subtests"],
        }
    else:
        suite = raptor.single_suite(r, speedometer3.SUITE_NAME, PREFIX)
        metrics = speedometer3.parse(suite, PREFIX)

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid iteration {iteration!r}")

    out = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "workload": workload,
            "aot_only": aot_only,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
        },
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
