#!/usr/bin/env python3
"""Emit aggregate JetStream startup latency by execution mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import json
import os
import statistics

import numpy as np
from figure_data import parse_data, table_json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_values

PROJECT_DIR = Path(__file__).resolve().parents[3]
from benchmark_stats import bootstrap_ratio_ci
from figure_style import load_configurations

CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")
ORDER = tuple(slug for slug, config in sorted(CONFIGS.items(), key=lambda item: item[1]["order"]))
BASELINE = "default-no-ion"
CANDIDATE = "aot-corpus"

data = parse_data(json.load(sys.stdin))
variants = [variant for variant in ORDER if variant in data.columns]
if not variants:
    raise SystemExit("startup_table: no known variants")
if BASELINE not in variants:
    raise SystemExit("startup_table: missing default-no-ion baseline")
if CANDIDATE not in variants:
    raise SystemExit("startup_table: missing aot-corpus candidate")

samples = {
    variant: run_values(data.columns[variant], "startup_geomean_ms")
    for variant in variants
}
means = {variant: statistics.fmean(values) for variant, values in samples.items()}
baseline = means[BASELINE]
rows = []
for variant in variants:
    values = samples[variant]
    rows.append(
        [
            CONFIGS[variant]["long"],
            round(means[variant], 3),
            round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
            round(means[variant] / baseline, 4),
        ]
    )

out_path = Path(sys.argv[1]) / "startup.json"
out_path.write_text(table_json(
    columns=[
        {"key": "variant", "label": "Variant", "align": "left", "format": "str"},
        {"key": "latency_ms", "label": "First (ms)", "align": "right", "format": "float"},
        {"key": "stdev_ms", "label": "stdev", "align": "right", "format": "float"},
        {"key": "ratio_over_baseline", "label": "vs Baseline", "align": "right", "format": "float"},
    ],
    rows=rows,
))

ratio = means[CANDIDATE] / baseline
_, lower_error, upper_error = bootstrap_ratio_ci(
    samples[CANDIDATE],
    samples[BASELINE],
    np.random.default_rng(0),
)
payload = json.loads(out_path.read_text())
payload.update(
    {
        "source_fossil": Path(__file__).resolve().parents[1].name,
        "workload": "jetstream3-startup",
        "baseline_variant": BASELINE,
        "candidate_variant": CANDIDATE,
        "baseline_latency_ms": means[BASELINE],
        "candidate_latency_ms": means[CANDIDATE],
        "aot_over_baseline_ratio": ratio,
        "aot_latency_reduction": 1.0 - ratio,
        "aot_latency_reduction_ci95_low": 1.0 - (ratio + upper_error),
        "aot_latency_reduction_ci95_high": 1.0 - (ratio - lower_error),
        "runs_per_variant": min(len(values) for values in samples.values()),
    }
)
out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
