#!/usr/bin/env python3
"""Emit a score table for one benchmark from any available policy subset."""

import json
import os
import sys
from pathlib import Path

POLICY_ORDER = ("default", "aot-only")


def scalar(column, key):
    value = column.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing scalar {key!r}")
    mean = value.get("mean")
    stddev = value.get("stddev")
    if not isinstance(mean, (int, float)) or not isinstance(stddev, (int, float)):
        raise ValueError(f"invalid scalar {key!r}")
    return float(mean), float(stddev)


def emit(workload, destination):
    data = json.load(sys.stdin)

    selected = {}
    for policy in POLICY_ORDER:
        variant = f"{workload}-{policy}"
        if variant in data:
            selected[policy] = scalar(data[variant], "score")
    if not selected:
        raise SystemExit(
            f"benchmark_table.py: no {workload!r} variants in analysis output"
        )

    default_score = selected.get("default", (None, None))[0]
    rows = []
    for policy in POLICY_ORDER:
        if policy not in selected:
            continue
        score, stddev = selected[policy]
        ratio = round(score / default_score, 4) if default_score else None
        rows.append([policy, round(score, 3), round(stddev, 3), ratio])

    payload = {
        "columns": [
            {"key": "policy", "label": "Execution", "format": "str", "align": "left"},
            {"key": "score", "label": "Score", "format": "float", "align": "right"},
            {"key": "score_stdev", "label": "Score stdev", "format": "float", "align": "right"},
            {"key": "ratio_over_default", "label": "vs default", "format": "float", "align": "right"},
        ],
        "rows": rows,
        "source_fossil": Path(__file__).resolve().parents[1].name,
        "workload": workload,
        "runs_per_variant": {
            policy: len(data[f"{workload}-{policy}"].get("runs", {}))
            for policy in selected
        },
    }
    if default_score and "aot-only" in selected:
        payload["aot_only_over_default_ratio"] = (
            selected["aot-only"][0] / default_score
        )

    destination.write_text(json.dumps(payload, indent=2) + "\n")

