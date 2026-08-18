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
            "variant": m.get("variant"),
            "commit": m.get("git", {}).get("commit", ""),
        },
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
