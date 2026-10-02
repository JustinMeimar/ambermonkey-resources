#!/usr/bin/env python3
"""Emit the Octane 2.0 tier-ladder table."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import json
import os
import statistics

from figure_data import parse_data, table_json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_values, validate_data

PROJECT_DIR = Path(__file__).resolve().parents[3]
from figure_style import load_configurations  # noqa: E402


BASELINE = "interp-only"
DEFAULT = "default"
CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")
VARIANT_ORDER = tuple(
    slug for slug, _ in sorted(CONFIGS.items(), key=lambda kv: kv[1]["order"])
)


def main():
    data = parse_data(json.load(sys.stdin))
    validate_data(data, baseline=BASELINE)

    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("octane_table: no known variants in analysis output")

    scores = {v: run_values(data.columns[v], "score") for v in variants}
    means = {v: statistics.fmean(scores[v]) for v in variants}
    stdevs = {
        v: statistics.stdev(scores[v]) if len(scores[v]) > 1 else 0.0
        for v in variants
    }

    base_score = means[BASELINE]
    default_score = means[DEFAULT] if DEFAULT in means else means[variants[-1]]

    columns = [
        {"key": "variant",           "label": "Variant",        "align": "left",  "format": "str"},
        {"key": "score",             "label": "Score",          "align": "right", "format": "float"},
        {"key": "score_stdev",       "label": "Score stdev",    "align": "right", "format": "float"},
        {"key": "ratio_over_interp", "label": "vs interp-only", "align": "right", "format": "float"},
        {"key": "ratio_over_default","label": "vs default",     "align": "right", "format": "float"},
    ]

    rows = [
        [
            v,
            round(means[v], 3),
            round(stdevs[v], 3),
            round(means[v] / base_score, 4),
            round(means[v] / default_score, 4),
        ]
        for v in variants
    ]

    aot = means.get("aot-corpus")
    aot_ic = means.get("aot-corpus-ic")
    interp = means.get(BASELINE)
    default = means.get(DEFAULT)
    runs_per_variant = min(len(scores[v]) for v in variants)

    out_path = Path(sys.argv[1]) / "perf.json"
    out_path.write_text(table_json(columns=columns, rows=rows))

    payload = json.loads(out_path.read_text())
    if aot is not None and interp is not None:
        payload["aot_over_interp_ratio"] = aot / interp
        payload["aot_over_interp_speedup"] = aot / interp - 1.0
    if aot is not None and default is not None:
        payload["aot_over_default_ratio"] = aot / default
    if aot_ic is not None and interp is not None:
        payload["aot_ic_over_interp_ratio"] = aot_ic / interp
        payload["aot_ic_over_interp_speedup"] = aot_ic / interp - 1.0
    if aot is not None and aot_ic is not None:
        aot_speedup = aot / interp - 1.0 if interp else 0.0
        ic_speedup = aot_ic / interp - 1.0 if interp else 0.0
        if aot_speedup > 0:
            payload["baseline_fn_share_of_aot_speedup"] = (
                (aot_speedup - ic_speedup) / aot_speedup
            )
            payload["ic_share_of_aot_speedup"] = ic_speedup / aot_speedup
    payload["source_fossil"] = Path(__file__).resolve().parents[1].name
    payload["workload"] = "octane2"
    payload["runs_per_variant"] = runs_per_variant
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
