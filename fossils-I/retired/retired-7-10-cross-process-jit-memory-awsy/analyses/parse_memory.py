#!/usr/bin/env python3
"""Per-observation normalizer for 7-10 (AWSY tp6 cross-process memory).

Reads the emit_summary.py blob from stdin and produces the metric tree the
fossil framework will aggregate across iterations, indexed under
`runs.run_XX` per the shared convention.
"""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import manifest

PREFIX = "parse_memory"

# Buckets emitted by scripts/emit_summary.py. Kept in a stable order for
# downstream table scripts.
BUCKETS = (
    "libxul_exec", "libxul_rodata", "libxul_rw",
    "anon_exec", "anon_rw", "other_file", "other_anon",
)

# Only these markers surface as top-level checkpoints. Everything else the
# sidecar happened to see (Start, StartSettled, TabsClosed*) is retained in
# the per-run tree but not in the top-level rollup.
PRIMARY_CHECKPOINTS = ("TabsOpen", "TabsOpenSettled", "TabsOpenForceGC",
                       "TabsClosedForceGC")

# Variant contract. Each variant asserts a binary path fragment, mozconfig
# fragment, and env flag expectations.
CONTRACT = {
    "awsy-tp6-stock":                {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": False},
    "awsy-tp6-stock-baseline":       {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": True},
    "awsy-tp6-aot":                  {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": False, "no_ion": False},
    "awsy-tp6-aot-only":             {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": True,  "no_ion": False},
    "awsy-tp6-stock-quick":          {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": False},
    "awsy-tp6-stock-baseline-quick": {"binary": "build-browser-release/dist/bin/firefox",     "mc": "browser-release.mozconfig",     "aot_only": False, "no_ion": True},
    "awsy-tp6-aot-quick":            {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": False, "no_ion": False},
    "awsy-tp6-aot-only-quick":       {"binary": "build-browser-release-aot/dist/bin/firefox", "mc": "browser-release-aot.mozconfig", "aot_only": True,  "no_ion": False},
}


def kind_of(variant):
    """Reduce a variant name to a JIT-config kind."""
    # Match stock-baseline before stock so the more specific prefix wins.
    if variant.startswith("awsy-tp6-stock-baseline"):
        return "stock-baseline"
    if variant.startswith("awsy-tp6-stock"):
        return "stock"
    if variant.startswith("awsy-tp6-aot-only"):
        return "aot-only"
    if variant.startswith("awsy-tp6-aot"):
        return "aot"
    manifest.fail(PREFIX, f"unclassified variant {variant!r}")


def validate_manifest(m):
    variant = m.get("variant")
    command = m.get("command", "")
    if variant not in CONTRACT:
        manifest.fail(PREFIX, f"unknown variant {variant!r}")
    c = CONTRACT[variant]
    if c["binary"] not in command:
        manifest.fail(PREFIX, f"{variant}: expected binary fragment {c['binary']!r} not in command")
    if c["mc"] not in command:
        manifest.fail(PREFIX, f"{variant}: expected mozconfig fragment {c['mc']!r} not in command")
    has_aot_only = "JIT_OPTION_aotOnly=1" in command
    if c["aot_only"] and not has_aot_only:
        manifest.fail(PREFIX, f"{variant}: JIT_OPTION_aotOnly=1 not present")
    if not c["aot_only"] and has_aot_only:
        manifest.fail(PREFIX, f"{variant}: forbidden JIT_OPTION_aotOnly=1 present")
    has_no_ion = "JIT_OPTION_ion=0" in command
    if c["no_ion"] and not has_no_ion:
        manifest.fail(PREFIX, f"{variant}: JIT_OPTION_ion=0 not present")
    if not c["no_ion"] and has_no_ion:
        manifest.fail(PREFIX, f"{variant}: forbidden JIT_OPTION_ion=0 present")
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
    """Convert emit_summary's kB fields to MB, keep vma_count."""
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
    """Sum bucket dicts across procs. `buckets_list` items may be missing keys."""
    out = zero_bucket_mb()
    for b in buckets_list:
        for k in out:
            out[k] += b.get(k, 0)
    for k in out:
        if k != "vma_count":
            out[k] = round(out[k], 4)
    return out


def reduce_checkpoint(cp):
    """Fold a per-checkpoint blob into a normalized metric tree.

    Per-proc rows are dict-of-dicts keyed by 'pid_<N>' (not a list) so the
    fossil_figures loader treats each proc row as a Metric subtree.
    """
    procs = cp.get("procs", [])
    content_procs = [p for p in procs if p.get("kind") == "content"]

    per_proc = {}
    for p in content_procs:
        buckets_mb = {b: bucket_kb_to_mb(p.get("buckets", {}).get(b, {}))
                      for b in BUCKETS}
        ae = buckets_mb["anon_exec"]
        lx = buckets_mb["libxul_exec"]
        per_proc[f"pid_{p['pid']}"] = {
            "pid": p["pid"],
            "sample_lag_us": p.get("sample_lag_us", 0),
            "anon_exec_rss_mb": ae["rss_mb"],
            "anon_exec_pss_mb": ae["pss_mb"],
            "anon_exec_uss_mb": ae["uss_mb"],
            "libxul_exec_rss_mb": lx["rss_mb"],
            "libxul_exec_pss_mb": lx["pss_mb"],
            "libxul_exec_uss_mb": lx["uss_mb"],
        }

    # Sum each bucket across content procs (raw kB → MB, then aggregate).
    totals = {}
    for b in BUCKETS:
        rows = [bucket_kb_to_mb(p.get("buckets", {}).get(b, {})) for p in content_procs]
        totals[b] = sum_buckets(rows)

    engine_pss = totals["anon_exec"]["pss_mb"] + totals["libxul_exec"]["pss_mb"]
    engine_rss = totals["anon_exec"]["rss_mb"] + totals["libxul_exec"]["rss_mb"]
    engine_uss = totals["anon_exec"]["uss_mb"] + totals["libxul_exec"]["uss_mb"]

    n = len(content_procs)
    per_proc_engine_pss_mb = round(engine_pss / n, 4) if n else 0.0

    return {
        "n_content_procs": n,
        "n_parent_procs": cp.get("n_parent_procs", 0),
        "engine_pss_mb": round(engine_pss, 4),
        "engine_rss_mb": round(engine_rss, 4),
        "engine_uss_mb": round(engine_uss, 4),
        "per_proc_engine_pss_mb": per_proc_engine_pss_mb,
        "totals": totals,
        "per_proc": per_proc,
    }


def maybe_warn(cp_out, warnings, name):
    """Populate soundness warnings on a normalized checkpoint."""
    for pid_key, p in cp_out["per_proc"].items():
        # Anonymous mappings on Linux: RSS == PSS == USS (all private).
        vals = [p["anon_exec_rss_mb"], p["anon_exec_pss_mb"], p["anon_exec_uss_mb"]]
        if max(vals) > 0.01 and (max(vals) - min(vals)) / max(vals) > 0.01:
            warnings.append(
                f"{name}: pid {p['pid']}: anon_exec RSS/PSS/USS diverge "
                f"({vals[0]}, {vals[1]}, {vals[2]})"
            )
    lx = cp_out["totals"]["libxul_exec"]
    if lx["private_dirty_mb"] * 100 > max(lx["shared_clean_mb"], 0.01):
        warnings.append(
            f"{name}: libxul_exec private_dirty {lx['private_dirty_mb']} MB "
            f"vs shared_clean {lx['shared_clean_mb']} MB — sharing may be broken"
        )


def main():
    m = manifest.load(PREFIX)
    variant = validate_manifest(m)
    kind = kind_of(variant)

    obs = json.load(sys.stdin)
    if obs.get("exit_code", 0) != 0:
        # Framework wrapping: single-observation results.json may carry either
        # shape. Guard on exit_code when present.
        pass
    stdout = obs.get("stdout")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)
    if not isinstance(stdout, str) or not stdout.strip():
        manifest.fail(PREFIX, "observation stdout is empty; emit_summary produced nothing")
    try:
        summary = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        manifest.fail(PREFIX, f"observation stdout is not JSON: {e}")

    checkpoints = summary.get("checkpoints", [])
    warnings = list(summary.get("warnings", []))

    # Latest-wins by short name (iteration 0 typically; if multiple iterations,
    # AWSY appends higher iterations that overwrite the previous).
    reduced = {}
    for cp in checkpoints:
        name = cp.get("name") or cp.get("marker")
        reduced[name] = reduce_checkpoint(cp)
        maybe_warn(reduced[name], warnings, name)

    # Only surface primary checkpoints in the top-level tree.
    primary = {name: reduced[name] for name in PRIMARY_CHECKPOINTS if name in reduced}
    if "TabsOpenForceGC" not in primary:
        warnings.append("TabsOpenForceGC checkpoint missing — primary metric unavailable")

    iteration = obs.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        manifest.fail(PREFIX, f"invalid observation iteration {iteration!r}")

    # Top-level scalar rollups anchor from TabsOpenForceGC (falling back to
    # TabsOpenSettled) — this is what tables aggregate against.
    anchor_name = "TabsOpenForceGC" if "TabsOpenForceGC" in primary \
                  else ("TabsOpenSettled" if "TabsOpenSettled" in primary else None)
    if anchor_name is None:
        manifest.fail(PREFIX, "no primary checkpoint present in observation")
    anchor = primary[anchor_name]

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
            "warnings": warnings[:20],  # cap; keep the analysis blob small
            "n_engine_procs_ever": summary.get("n_engine_procs_ever", 0),
            "n_sidecar_procs_ever": summary.get("n_sidecar_procs_ever", 0),
        },
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
