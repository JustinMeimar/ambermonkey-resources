#!/usr/bin/env python3
"""Aggregate AOT_TIMING content-process records from one cpstartup observation.

Emits per-artifact-class metrics: mean install/compile time per call, mean
install/compile count per content process, and mean AOT image bytes per
content process."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "aot_attachment_cost"
TIMING_RE = re.compile(r"AOT_TIMING\s+(\{.*\})")

ARTIFACTS = (
    # (row-key, install-phase, compile-phase, image-counter)
    ("interpreter",      "interpreter_install", "interpreter_generate", "interpreter_image_bytes"),
    ("baseline_scripts", "baseline_install",    "baseline_compile",     "baseline_image_bytes"),
    ("ic_stubs",         "ic_install",          "ic_compile",           "ic_image_bytes"),
)


def command_flag(command, name, value="true"):
    pattern = rf"(?:^|\s){re.escape(name)}={re.escape(value)}(?=\s|$)"
    return re.search(pattern, command) is not None


def validate_manifest(record):
    variant = record.get("variant")
    command = record.get("command")
    if not isinstance(variant, str) or not variant:
        manifest.fail(PREFIX, f"invalid manifest variant {variant!r}")
    if not isinstance(command, str) or not command:
        manifest.fail(PREFIX, f"{variant}: manifest command is missing")
    if "talos-test -a cpstartup" not in command or not command_flag(
        command, "JS_AOT_TIMING", "1"
    ):
        manifest.fail(PREFIX, f"{variant}: cpstartup timing is not enabled")

    use_aot = command_flag(command, "JIT_OPTION_useAOTImage")
    use_aot_ic = command_flag(command, "JIT_OPTION_useAOTIC")
    use_aot_baseline = command_flag(command, "JIT_OPTION_useAOTBaseline")
    aot_only = command_flag(command, "JIT_OPTION_aotOnly")
    ion_off = command_flag(command, "JIT_OPTION_ion", "false")
    native_regex_off = command_flag(command, "JIT_OPTION_nativeRegExp", "false")

    if not ion_off or not native_regex_off:
        manifest.fail(PREFIX, f"{variant}: execution controls are not matched")
    if variant == "default-no-ion" and (
        use_aot or use_aot_ic or use_aot_baseline or aot_only
    ):
        manifest.fail(PREFIX, f"{variant}: AOT execution is enabled")
    if variant == "aot-corpus-ic" and not (
        use_aot_ic and not use_aot and not use_aot_baseline and aot_only
    ):
        manifest.fail(PREFIX, f"{variant}: incomplete IC-only policy")
    if variant == "aot-corpus" and not (use_aot and aot_only):
        manifest.fail(PREFIX, f"{variant}: incomplete AOT-only policy")

    return variant, command


def obs_lines(obs, key):
    lines = obs.get(key) or []
    if isinstance(lines, str):
        return lines.splitlines()
    return lines


def content_records(lines):
    records = []
    for line in lines:
        match = TIMING_RE.search(line)
        if not match:
            continue
        try:
            rec = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if rec.get("process_type") == "content":
            records.append(rec)
    return records


def main():
    m = manifest.load(PREFIX)
    variant, _ = validate_manifest(m)
    obs = json.load(sys.stdin)

    lines = obs_lines(obs, "stdout") + obs_lines(obs, "stderr")
    records = content_records(lines)
    if not records:
        manifest.fail(PREFIX, "no content-process AOT_TIMING records")

    n = len(records)
    phases = {}
    counters = {}
    for rec in records:
        for name, info in rec.get("phases", {}).items():
            calls, ns = phases.get(name, (0, 0))
            phases[name] = (calls + info["calls"], ns + info["total_ns"])
        for name, value in rec.get("counters", {}).items():
            counters[name] = counters.get(name, 0) + value

    if variant == "aot-corpus-ic":
        baseline_installs, _ = phases.get("baseline_install", (0, 0))
        if baseline_installs:
            manifest.fail(
                PREFIX,
                f"{variant}: observed {baseline_installs} Baseline-body attachments",
            )

    def per_call_us(phase):
        calls, ns = phases.get(phase, (0, 0))
        return (ns / calls / 1000.0) if calls else 0.0

    def per_proc(value):
        return value / n

    artifacts = {}
    for key, install_phase, compile_phase, image_counter in ARTIFACTS:
        install_calls, _ = phases.get(install_phase, (0, 0))
        compile_calls, _ = phases.get(compile_phase, (0, 0))
        artifacts[key] = {
            "install_us_per_call":  per_call_us(install_phase),
            "compile_us_per_call":  per_call_us(compile_phase),
            "installs_per_proc":    per_proc(install_calls),
            "compiles_per_proc":    per_proc(compile_calls),
            "image_bytes_per_proc": per_proc(counters.get(image_counter, 0)),
        }

    out = {
        "artifacts": artifacts,
        "content_processes": n,
        "meta": {
            "variant": variant,
            "commit": m.get("git", {}).get("commit", ""),
        },
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
