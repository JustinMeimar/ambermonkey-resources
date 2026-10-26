#!/usr/bin/env python3
"""Per-observation normalizer for 7-11 (Speedometer 3 memory).

Consumes the emit_summary.py blob from stdin; produces the fossil metric
tree for the two synthetic checkpoints Peak and Final."""

import json
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from benchmarks import manifest

PREFIX = "parse_memory"

BUCKETS = (
    "libxul_exec", "libxul_rodata", "libxul_rw",
    "anon_exec", "anon_rw", "other_file", "other_anon",
)

PRIMARY_CHECKPOINTS = ("Peak", "Final")

CONTRACT = {
    "interp-only":    {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": False, "no_backend": True},
    "default":        {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": False, "no_backend": False},
    "default-no-ion": {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": True,  "no_backend": False},
    # Historical AmberMonkey+Ion records remain valid, but this variant is no
    # longer offered by fossil.toml or included in the presentation outputs.
    "aot":            {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": False, "no_ion": False, "no_backend": False},
    "aot-corpus":     {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": True,  "no_ion": True,  "no_backend": False},
}


def kind_of(variant):
    if variant in CONTRACT:
        return variant
    manifest.fail(PREFIX, f"unclassified variant {variant!r}")


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command", "")
    if variant not in CONTRACT:
        manifest.fail(PREFIX, f"unknown variant {variant!r}")
    c = CONTRACT[variant]
    tokens = shlex.split(command)
    suffix = 'AOT' if variant in ('aot', 'aot-corpus') else 'RELEASE'
    binary = os.environ.get(f'AMBERMONKEY_BIN_{suffix}')
    mozconfig = os.environ.get(f'AMBERMONKEY_MOZCONFIG_{suffix}')
    packaged_binary = binary and any(
        tokens[i:i + 2] == ['--binary', binary] for i in range(len(tokens) - 1))
    if c['binary'] not in command and not packaged_binary:
        manifest.fail(PREFIX, f"{variant}: expected binary {binary or c['binary']!r}")
    if c['mc'] not in command and not (mozconfig and f'MOZCONFIG={mozconfig}' in tokens):
        manifest.fail(PREFIX, f"{variant}: expected mozconfig {mozconfig or c['mc']!r}")
    has_aot_only = "JIT_OPTION_aotOnly=1" in command or "JIT_OPTION_aotOnly=true" in command
    if c["aot_only"] and not has_aot_only:
        manifest.fail(PREFIX, f"{variant}: JIT_OPTION_aotOnly not present")
    if not c["aot_only"] and has_aot_only:
        manifest.fail(PREFIX, f"{variant}: forbidden JIT_OPTION_aotOnly present")
    if "JIT_OPTION_ion=0" in command:
        manifest.fail(
            PREFIX,
            f"{variant}: JIT_OPTION_ion=0 does not disable Ion; use "
            "javascript.options.ion=false or JIT_OPTION_ion=false",
        )
    has_no_ion = (
        "JIT_OPTION_ion=false" in command
        or "JIT_OPTION_ion=no" in command
        or "javascript.options.ion=false" in command
    )
    if c["no_ion"] and not has_no_ion:
        manifest.fail(PREFIX, f"{variant}: no-Ion flag not present")
    if not c["no_ion"] and has_no_ion:
        manifest.fail(PREFIX, f"{variant}: forbidden no-Ion flag present")
    has_no_backend = "JIT_OPTION_disableJitBackend=1" in command or "JIT_OPTION_disableJitBackend=true" in command
    if c["no_backend"] and not has_no_backend:
        manifest.fail(PREFIX, f"{variant}: disableJitBackend flag not present")
    if not c["no_backend"] and has_no_backend:
        manifest.fail(PREFIX, f"{variant}: forbidden disableJitBackend flag present")
    return variant


def to_mb(kb):
    return round(kb / 1024.0, 4)


def zero_bucket_mb():
    return {
        "size_mb": 0.0, "rss_mb": 0.0, "pss_mb": 0.0,
        "shared_clean_mb": 0.0, "shared_dirty_mb": 0.0,
        "private_clean_mb": 0.0, "private_dirty_mb": 0.0,
        "referenced_mb": 0.0, "anonymous_mb": 0.0,
        "uss_mb": 0.0, "vma_count": 0,
    }


def bucket_kb_to_mb(bkt):
    return {
        "size_mb":         to_mb(bkt.get("size_kb", 0)),
        "rss_mb":          to_mb(bkt.get("rss_kb", 0)),
        "pss_mb":          to_mb(bkt.get("pss_kb", 0)),
        "shared_clean_mb": to_mb(bkt.get("shared_clean_kb", 0)),
        "shared_dirty_mb": to_mb(bkt.get("shared_dirty_kb", 0)),
        "private_clean_mb":to_mb(bkt.get("private_clean_kb", 0)),
        "private_dirty_mb":to_mb(bkt.get("private_dirty_kb", 0)),
        "referenced_mb":   to_mb(bkt.get("referenced_kb", 0)),
        "anonymous_mb":    to_mb(bkt.get("anonymous_kb", 0)),
        "uss_mb":          to_mb(bkt.get("uss_kb", 0)),
        "vma_count":       int(bkt.get("vma_count", 0)),
    }


def sum_buckets(buckets_list):
    out = zero_bucket_mb()
    for b in buckets_list:
        for k in out:
            out[k] += b.get(k, 0)
    for k in out:
        if k != "vma_count":
            out[k] = round(out[k], 4)
    return out


def is_browser_content_process(proc):
    """Select Gecko browser-content processes, excluding other child types.

    Older records classified every ``-contentproc`` child (including socket,
    RDD, utility, and forkserver processes) as content. Their preserved command
    lines let us apply the correct definition during analysis as well as in new
    samples.
    """
    return (
        proc.get("kind") == "content"
        and "-isForBrowser" in proc.get("cmd_hint", "")
    )


def reduce_checkpoint(cp):
    procs = cp.get("procs", [])
    content = [p for p in procs if is_browser_content_process(p)]

    per_proc = {}
    for p in content:
        buckets_mb = {b: bucket_kb_to_mb(p.get("buckets", {}).get(b, {}))
                      for b in BUCKETS}
        ae = buckets_mb["anon_exec"]
        lx = buckets_mb["libxul_exec"]
        per_proc[f"pid_{p['pid']}"] = {
            "pid": p["pid"],
            "anon_exec_pss_mb": ae["pss_mb"],
            "anon_exec_rss_mb": ae["rss_mb"],
            "libxul_exec_pss_mb": lx["pss_mb"],
            "libxul_exec_rss_mb": lx["rss_mb"],
        }

    totals = {}
    for b in BUCKETS:
        rows = [bucket_kb_to_mb(p.get("buckets", {}).get(b, {})) for p in content]
        totals[b] = sum_buckets(rows)

    engine_pss = totals["anon_exec"]["pss_mb"] + totals["libxul_exec"]["pss_mb"]
    engine_rss = totals["anon_exec"]["rss_mb"] + totals["libxul_exec"]["rss_mb"]
    engine_uss = totals["anon_exec"]["uss_mb"] + totals["libxul_exec"]["uss_mb"]

    n = len(content)
    per_proc_engine_pss = round(engine_pss / n, 4) if n else 0.0

    return {
        "n_content_procs": n,
        "n_parent_procs": cp.get("n_parent_procs", 0),
        "engine_pss_mb": round(engine_pss, 4),
        "engine_rss_mb": round(engine_rss, 4),
        "engine_uss_mb": round(engine_uss, 4),
        "per_proc_engine_pss_mb": per_proc_engine_pss,
        "totals": totals,
        "per_proc": per_proc,
    }


def main():
    obs = json.load(sys.stdin)
    m = manifest.load(PREFIX, run_dir=sys.argv[2], observation=obs)
    variant = validate_manifest(m)
    kind = kind_of(variant)

    stdout = obs.get("stdout")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    if not isinstance(stdout, str) or not stdout.strip():
        manifest.fail(PREFIX, "observation stdout is empty; emit_summary produced nothing")
    try:
        summary = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        manifest.fail(PREFIX, f"observation stdout is not JSON: {e}")

    warnings = list(summary.get("warnings", []))
    checkpoints = summary.get("checkpoints", [])
    reduced = {}
    for cp in checkpoints:
        name = cp.get("name") or cp.get("marker")
        reduced[name] = reduce_checkpoint(cp)

    primary = {name: reduced[name] for name in PRIMARY_CHECKPOINTS if name in reduced}
    anchor_name = "Peak" if "Peak" in primary else ("Final" if "Final" in primary else None)
    if anchor_name is None:
        manifest.fail(PREFIX, "no primary checkpoint present")
    anchor = primary[anchor_name]

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

    sample = {
        "kind": kind,
        "anchor_checkpoint": anchor_name,
        "n_content_procs": anchor["n_content_procs"],
        "engine_pss_mb": anchor["engine_pss_mb"],
        "engine_rss_mb": anchor["engine_rss_mb"],
        "engine_uss_mb": anchor["engine_uss_mb"],
        "per_proc_engine_pss_mb": anchor["per_proc_engine_pss_mb"],
        "checkpoints": primary,
    }
    output = {
        **sample,
        "runs": {f"run_{iteration:02d}": sample},
        "meta": {
            "variant": variant,
            "kind": kind,
            "commit": m.get("git", {}).get("commit", ""),
            "iterations": m.get("iterations", 0),
            "warnings": warnings[:20],
            "n_engine_procs_ever": summary.get("n_engine_procs_ever", 0),
            "n_sidecar_procs_ever": summary.get("n_sidecar_procs_ever", 0),
            "n_intervals": summary.get("n_intervals", 0),
            "peak_interval": summary.get("peak_interval"),
            "final_interval": summary.get("final_interval"),
        },
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
