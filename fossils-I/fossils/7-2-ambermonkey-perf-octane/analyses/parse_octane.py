#!/usr/bin/env python3
"""Parse one Octane jsshell observation.

Octane's run.js writes lines of the form:
    Richards: 12345
    DeltaBlue: 6789
    ...
    ----
    Score (version 9): 5432

We collect every ``<name>: <score>`` line as a per-workload score and the
final ``Score (version N): <score>`` as the aggregate. The observation
envelope from fossil is a JSON object whose ``stderr`` array (jsshell
prints to stdout, fossil merges to stderr for shell benchmarks; both
``stdout`` and ``stderr`` are scanned to be safe) contains the raw lines.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from benchmarks import manifest, octane  # noqa: E402

PREFIX = "parse_octane.py"
SYNTHETIC_PREFIX = "FOSSIL_SYNTHETIC_METRICS="



def command_has(command, needle):
    return bool(re.search(rf"(?:^|\s){re.escape(needle)}(?=\s|$)", command))


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")

    wasm_disabled = "--wasm-compiler=none" in command
    aot = command_has(command, "--aot")
    aot_only = command_has(command, "--aot-only")
    aot_skip_baseline_fn = manifest.command_flag(command, "JIT_OPTION_aotSkipBaselineFn")
    jit_backend_disabled = command_has(command, "--no-jit-backend")
    ion_disabled = command_has(command, "--no-ion")

    if not wasm_disabled:
        manifest.fail(PREFIX, f"{variant}: --wasm-compiler=none was not set")
    if aot_only and not aot:
        manifest.fail(PREFIX, f"{variant}: --aot-only requires --aot")
    if variant == "interp-only" and not jit_backend_disabled:
        manifest.fail(PREFIX, "interp-only: --no-jit-backend was not set")
    if variant == "aot-corpus-ic" and not aot_skip_baseline_fn:
        manifest.fail(PREFIX, "aot-corpus-ic: JIT_OPTION_aotSkipBaselineFn was not set")

    if aot_only:
        aot_policy = "aot-only"
    elif aot:
        aot_policy = "runtime-fallback"
    else:
        aot_policy = "disabled"

    execution = {
        "aot_image": "enabled" if aot else "disabled",
        "aot_policy": aot_policy,
        "aot_baseline_functions": "disabled" if aot_skip_baseline_fn else "enabled",
        "ion": (
            "unavailable"
            if jit_backend_disabled
            else "disabled" if ion_disabled else "enabled"
        ),
        "jit_backend": "disabled" if jit_backend_disabled else "enabled",
        "wasm": "disabled",
    }
    return variant, execution




observation = json.load(sys.stdin)
m = manifest.load(PREFIX, run_dir=sys.argv[2], observation=observation)
variant, execution = validate_manifest(m)

lines = octane.lines(observation)
synthetic = next(
    (
        json.loads(line.removeprefix(SYNTHETIC_PREFIX))
        for line in lines
        if line.startswith(SYNTHETIC_PREFIX)
    ),
    None,
)
if synthetic is None:
    workload_scores, aggregate = octane.parse_scores(lines, PREFIX)
else:
    workload_scores = synthetic["workload_scores"]
    aggregate = synthetic["score"]
if aggregate is None:
    manifest.fail(PREFIX, f"{variant}: no 'Score (version N): X' line in output")
if not workload_scores:
    manifest.fail(PREFIX, f"{variant}: no per-workload result lines in output")

iteration = observation.get("iteration")
if not isinstance(iteration, int) or iteration < 1:
    manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

sample = {
    "score": aggregate,
    "workload_scores": workload_scores,
}
output = {
    "score": aggregate,
    "workload_scores": workload_scores,
    "runs": {f"run_{iteration:02d}": sample},
    "meta": {
        "variant": variant,
        "commit": m.get("git", {}).get("commit", ""),
        "iterations": m.get("iterations"),
        "execution": execution,
        "provenance": "synthetic-placeholder" if synthetic else "measured",
    },
}

json.dump(output, sys.stdout, sort_keys=True)
