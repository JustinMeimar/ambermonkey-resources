#!/usr/bin/env python3
"""Parse peak RSS / anon / anon-exec memory metrics from a shell-memory observation."""

import json
import os
import re
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "shell_memory"

VARIANT_RE = re.compile(r"^(?P<bench>[a-z0-9-]+)-(?P<kind>interp|baseline|stock|aot-only|aot)$")
RSS_RE = re.compile(r"peak_rss_kb=(\d+)")
ANON_RE = re.compile(r"peak_anon_kb=(\d+)")
ANON_EXEC_RE = re.compile(r"peak_anon_exec_kb=(\d+)")

BENCHES = {
    "richards", "deltablue", "crypto", "raytrace", "earley-boyer", "regexp",
    "splay", "navier-stokes", "pdfjs", "mandreel", "gbemu", "code-load",
    "box2d", "zlib", "typescript",
}

FLAG_CONTRACT = {
    "interp":   {"require": ["--no-jit-backend"],  "forbid": ["--aot", "--aot-only", "--no-ion"]},
    "baseline": {"require": ["--no-ion"],          "forbid": ["--aot", "--aot-only", "--no-jit-backend"]},
    "stock":    {"require": [],                     "forbid": ["--aot", "--aot-only", "--no-ion", "--no-jit-backend"]},
    "aot":      {"require": ["--aot"],              "forbid": ["--aot-only", "--no-ion", "--no-jit-backend"]},
    "aot-only": {"require": ["--aot", "--aot-only"], "forbid": ["--no-ion", "--no-jit-backend"]},
}


def has_flag(cmd, flag):
    return any(tok == flag for tok in cmd.split())


def validate(m):
    variant = m.get("variant", "")
    match = VARIANT_RE.match(variant)
    if not match:
        manifest.fail(PREFIX, f"unexpected variant {variant!r}")
    bench = match.group("bench")
    kind = match.group("kind")
    if bench not in BENCHES:
        manifest.fail(PREFIX, f"{variant}: unknown benchmark {bench!r}")
    cmd = m.get("command", "")
    if f"run-{bench}.js" not in cmd:
        manifest.fail(PREFIX, f"{variant}: run-{bench}.js not in command")
    contract = FLAG_CONTRACT[kind]
    for flag in contract["require"]:
        if not has_flag(cmd, flag):
            manifest.fail(PREFIX, f"{variant}: missing required flag {flag}")
    for flag in contract["forbid"]:
        if has_flag(cmd, flag):
            manifest.fail(PREFIX, f"{variant}: forbidden flag present {flag}")
    return variant, bench, kind


def main():
    m = manifest.load(PREFIX)
    variant, bench, kind = validate(m)
    obs = json.load(sys.stdin)
    stderr = obs.get("stderr", "")
    lines = stderr if isinstance(stderr, list) else stderr.splitlines()

    rss = anon = anon_exec = None
    for line in lines:
        mm = RSS_RE.search(line)
        if mm:
            rss = int(mm.group(1))
        mm = ANON_RE.search(line)
        if mm:
            anon = int(mm.group(1))
        mm = ANON_EXEC_RE.search(line)
        if mm:
            anon_exec = int(mm.group(1))
    if rss is None:
        manifest.fail(PREFIX, "peak_rss_kb not found in stderr; wrapper failed")
    if anon is None:
        manifest.fail(PREFIX, "peak_anon_kb not found in stderr; wrapper failed")
    if anon_exec is None:
        manifest.fail(PREFIX, "peak_anon_exec_kb not found in stderr; wrapper failed")

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid iteration {iteration!r}")

    metrics = {
        "peak_rss_kb": rss,
        "peak_rss_mb": round(rss / 1024, 3),
        "peak_anon_kb": anon,
        "peak_anon_mb": round(anon / 1024, 3),
        "peak_anon_exec_kb": anon_exec,
        "peak_anon_exec_mb": round(anon_exec / 1024, 3),
        "bench": bench,
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
