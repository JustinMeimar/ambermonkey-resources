#!/usr/bin/env python3
"""Plot first-iteration latency relative to the Baseline JIT."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import os
import statistics

import matplotlib.pyplot as plt
from figure_data import parse_data

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_values

PROJECT_DIR = Path(__file__).resolve().parents[3]
from figure_style import apply_amber_style, figure_size, load_configurations

BASELINE = "default-no-ion"
CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")
ORDER = tuple(slug for slug, config in sorted(CONFIGS.items(), key=lambda item: item[1]["order"]))

apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
if BASELINE not in data.columns:
    raise ValueError(f"missing {BASELINE!r} baseline")

unknown = set(data.column_names) - set(ORDER)
if unknown:
    raise ValueError(f"unexpected variants: {sorted(unknown)}")
variants = [variant for variant in ORDER if variant in data.columns]
samples = {
    variant: run_values(data.columns[variant], "startup_geomean_ms")
    for variant in variants
}
baseline = statistics.fmean(samples[BASELINE])
means = [statistics.fmean(samples[variant]) / baseline for variant in variants]
errors = [
    statistics.stdev(value / baseline for value in samples[variant])
    if len(samples[variant]) > 1 else 0.0
    for variant in variants
]

fig, ax = plt.subplots(figsize=figure_size("single", 2.1))
positions = range(len(variants))
ax.bar(
    positions,
    means,
    width=0.68,
    yerr=[error or 0 for error in errors],
    color=[CONFIGS[variant]["color"] for variant in variants],
    edgecolor="#555555",
    linewidth=0.4,
    capsize=2.5,
    zorder=3,
)
ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--", zorder=2)
ax.set_xticks(list(positions))
ax.set_xticklabels([CONFIGS[variant]["short"] for variant in variants])
ax.set_ylabel("First-iteration latency\n(relative to Baseline JIT)")
ax.set_xlim(-0.6, len(variants) - 0.4)
ax.set_ylim(0, max(mean + error for mean, error in zip(means, errors)) * 1.12)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0)
fig.subplots_adjust(left=0.22, right=0.985, top=0.95, bottom=0.18)
fig.savefig(Path(sys.argv[1]) / "startup-bars.png", dpi=300)
fig.savefig(Path(sys.argv[1]) / "startup-bars.pdf")
