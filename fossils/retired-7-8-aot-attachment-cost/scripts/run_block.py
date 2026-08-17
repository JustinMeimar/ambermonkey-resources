#!/usr/bin/env python3
"""Run cpstartup twice per block — once without an AOT image and once with —
with JS_AOT_TIMING on so both cells emit per-artifact phase timings."""

import argparse
import hashlib
import json
import os
import random
import re
import secrets
import subprocess
import sys
from pathlib import Path


TIMING_RE = re.compile(r"AOT_TIMING\s+(\{.*\})")
PERFHERDER_MARKER = "PERFHERDER_DATA:"
CELLS = (
    ("runtime", False),
    ("aot", True),
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--firefox", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--mozconfig", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    return parser.parse_args()


def clean_environment():
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("JIT_OPTION_") or key.startswith("JS_AOT_"):
            env.pop(key)
    for key in ("IONFLAGS", "MOZCONFIG", "MOZ_HEADLESS", "MOZ_DISABLE_CONTENT_SANDBOX"):
        env.pop(key, None)
    return env


def find_perfherder(lines):
    for line in reversed(lines):
        marker = line.find(PERFHERDER_MARKER)
        if marker >= 0:
            return json.loads(line[marker + len(PERFHERDER_MARKER) :].strip())
    raise RuntimeError("Talos output did not contain PERFHERDER_DATA")


def timing_records(lines):
    records = []
    for line in lines:
        match = TIMING_RE.search(line)
        if match:
            records.append(json.loads(match.group(1)))
    return records


def run_cell(args, name, use_aot):
    env = clean_environment()
    env["MOZCONFIG"] = str(args.mozconfig)
    env["JS_AOT_TIMING"] = "1"
    if use_aot:
        env["JIT_OPTION_useAOTImage"] = "true"

    command = ["./mach", "talos-test", "-a", "cpstartup"]
    process = subprocess.Popen(
        command,
        cwd=args.firefox,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    lines = []
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n")
        lines.append(line)
        print(f"[{name}] {line}", file=sys.stderr, flush=True)
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"{name}: Talos exited with status {return_code}")

    records = [r for r in timing_records(lines) if r.get("process_type") == "content"]
    if not records:
        raise RuntimeError(f"{name}: no content-process AOT_TIMING records")

    return {
        "use_aot_image": use_aot,
        "perfherder": find_perfherder(lines),
        "timing_records": records,
    }


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    args = parse_args()
    args.firefox = args.firefox.resolve()
    args.binary = args.binary.resolve()
    args.mozconfig = args.mozconfig.resolve()
    if not args.binary.is_file():
        raise SystemExit(f"Firefox binary not found: {args.binary}")

    seed = args.seed if args.seed is not None else secrets.randbits(64)
    order = list(CELLS)
    random.Random(seed).shuffle(order)
    cells = {}
    for name, use_aot in order:
        cells[name] = run_cell(args, name, use_aot)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=args.firefox,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    json.dump(
        {
            "seed": seed,
            "order": [cell[0] for cell in order],
            "cells": cells,
            "browser": {
                "binary": str(args.binary),
                "sha256": sha256(args.binary),
                "firefox_commit": commit,
                "mozconfig": str(args.mozconfig),
            },
        },
        sys.stdout,
        separators=(",", ":"),
    )
    print()


if __name__ == "__main__":
    main()
