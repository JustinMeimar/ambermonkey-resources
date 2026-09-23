#!/usr/bin/env python3
"""Parse per-worker peak RSS and anon-exec residency from a shell scaling observation."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "shell_rss"

VARIANT_RE = re.compile(r"^n(\d+)-(stock-base|stock-full|aot-restricted|aot-full)$")
RSS_RE = re.compile(r"peak_rss_kb=(\d+)")
ANON_EXEC_RE = re.compile(r"peak_anon_exec_kb=(\d+)")

# For each variant kind, the flags that must and must not appear in the command.
FLAG_CONTRACT = {
    "stock-base":     {"require": ["--no-ion"],                             "forbid": ["--aot", "--aot-only"]},
    "stock-full":     {"require": [],                                        "forbid": ["--aot", "--aot-only", "--no-ion"]},
    "aot-restricted": {"require": ["--aot", "--aot-only", "--no-ion"],       "forbid": []},
    "aot-full":       {"require": ["--aot"],                                 "forbid": ["--aot-only", "--no-ion"]},
}


def has_flag(cmd, flag):
    """Whole-token match so --aot does not match --aot-only."""
    return any(tok == flag for tok in cmd.split())


def validate(m):
    variant = m.get("variant", "")
    match = VARIANT_RE.match(variant)
    if not match:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    workers = int(match.group(1))
    kind = match.group(2)
    cmd = m.get("command", "")

    contract = FLAG_CONTRACT[kind]
    for flag in contract["require"]:
        if not has_flag(cmd, flag):
            manifest.fail(PREFIX, f"{variant}: missing required flag {flag}")
    for flag in contract["forbid"]:
        if has_flag(cmd, flag):
            manifest.fail(PREFIX, f"{variant}: forbidden flag present {flag}")
    if f"-- {workers}" not in cmd:
        manifest.fail(PREFIX, f"{variant}: worker arg {workers} not in command")
    return variant, workers, kind


def main():
    m = manifest.load(PREFIX)
    variant, workers, kind = validate(m)
    obs = json.load(sys.stdin)
    stderr = obs.get("stderr", "")
    lines = stderr if isinstance(stderr, list) else stderr.splitlines()

    peak = None
    anon = None
    for line in lines:
        mm = RSS_RE.search(line)
        if mm:
            peak = int(mm.group(1))
        mm = ANON_EXEC_RE.search(line)
        if mm:
            anon = int(mm.group(1))
    if peak is None:
        manifest.fail(PREFIX, "peak_rss_kb not found in stderr; wrapper failed")
    if anon is None:
        manifest.fail(PREFIX, "peak_anon_exec_kb not found in stderr; wrapper failed")

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid iteration {iteration!r}")

    metrics = {
        "peak_rss_kb": peak,
        "peak_rss_mb": round(peak / 1024, 3),
        "peak_anon_exec_kb": anon,
        "peak_anon_exec_mb": round(anon / 1024, 3),
        "workers": workers,
        "kind": kind,
    }
    out = {
        **metrics,
        "runs": {f"run_{iteration:02d}": metrics},
        "meta": {
            "variant": variant,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations"),
        },
    }
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
