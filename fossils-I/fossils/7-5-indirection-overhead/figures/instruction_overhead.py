#!/usr/bin/env python3
"""Retired-instruction overhead for indirection-sensitive paths."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import os

import matplotlib.pyplot as plt
import numpy as np
from figure_data import parse_data

PROJECT_DIR = Path(__file__).resolve().parents[3]
from figure_style import (  # noqa: E402
    BAR_EDGE_WIDTH,
    BAR_GROUP_WIDTH,
    FONT_SIZES,
    GEOMEAN_GROUP_GAP,
    apply_amber_style,
    darken_color,
    figure_size,
    save_at_declared_size,
)

BASELINE = "baseline-jit"
VARIANT_ORDER = ("am-rit", "am-rit-nl", "am-rit-nl-vm")
VARIANT_LABELS = {
    "am-rit": "Pure RIT",
    "am-rit-nl": "Linker Relocs",
    "am-rit-nl-vm": "Linker Relocs + Value Mirroring (AmberMonkey)",
}
# An opaque amber--rose--burgundy sequence preserves the paper's warm palette
# while separating the variants by luminance when printed in grayscale.
VARIANT_COLORS = {
    "am-rit": "#E69F00",
    "am-rit-nl": "#CC6677",
    "am-rit-nl-vm": "#8C1D40",
}
ROWS = (
    ("Stack + ABI", "benchmarks.stack-abi-call.insns_per_iter"),
    ("Stack", "benchmarks.stack-check.insns_per_iter"),
    ("Pre-barrier + ABI", "benchmarks.prebarrier-abi-call.insns_per_iter"),
    ("Pre-barrier", "benchmarks.prebarrier.insns_per_iter"),
    ("VM call", "benchmarks.vm-call.insns_per_iter"),
    ("ABI call", "benchmarks.abi-call.insns_per_iter"),
    ("Interrupt", "benchmarks.interrupt-check.insns_per_iter"),
    ("Geo Mean", "aggregates.targeted_insns_per_iter_geomean"),
)
SAMPLE_COUNT = "meta.retained_observations_per_benchmark"
Z_95 = 1.96


def ratio_interval(value, baseline, value_n, baseline_n):
    ratio = value.mean / baseline.mean
    log_se = np.hypot(
        value.stddev / (np.sqrt(value_n) * value.mean),
        baseline.stddev / (np.sqrt(baseline_n) * baseline.mean),
    )
    lower = ratio * np.exp(-Z_95 * log_se)
    upper = ratio * np.exp(Z_95 * log_se)
    return (
        (ratio - 1.0) * 100.0,
        (ratio - lower) * 100.0,
        (upper - ratio) * 100.0,
    )


apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
table = data.flat_table()
unknown = set(data.column_names) - {BASELINE, *VARIANT_ORDER}
if unknown:
    raise ValueError(f"unexpected variants: {sorted(unknown)}")
if BASELINE not in table:
    raise ValueError(f"missing required baseline {BASELINE!r}")

variants = [variant for variant in VARIANT_ORDER if variant in table]
if not variants:
    raise ValueError("at least one AmberMonkey variant is required")
for variant in [BASELINE, *variants]:
    for _, metric in ROWS:
        if metric not in table[variant]:
            raise ValueError(f"{variant}: missing metric {metric}")
    if SAMPLE_COUNT not in table[variant]:
        raise ValueError(f"{variant}: missing metric {SAMPLE_COUNT}")

baseline_n = int(table[BASELINE][SAMPLE_COUNT].mean)
results = {}
for variant in variants:
    variant_n = int(table[variant][SAMPLE_COUNT].mean)
    results[variant] = [
        ratio_interval(
            table[variant][metric],
            table[BASELINE][metric],
            variant_n,
            baseline_n,
        )
        for _, metric in ROWS
    ]

n_variants = len(variants)
bar_width = BAR_GROUP_WIDTH / n_variants
geomean_bar_width = bar_width
x_group = np.arange(len(ROWS), dtype=float)
x_group[-1] += GEOMEAN_GROUP_GAP
fig, ax = plt.subplots(figsize=figure_size("single", 2.00))

lowest = 0.0
highest = 0.0
geomean_annotations = []
for i, variant in enumerate(variants):
    offset = (i - (n_variants - 1) / 2) * bar_width
    geomean_offset = (i - (n_variants - 1) / 2) * geomean_bar_width
    xs = x_group[:-1] + offset
    geomean_x = x_group[-1] + geomean_offset
    overheads = [result[0] for result in results[variant]]
    lower_errors = [result[1] for result in results[variant]]
    upper_errors = [result[2] for result in results[variant]]
    lowest = min(
        lowest,
        min(value - error for value, error in zip(overheads, lower_errors)),
    )
    highest = max(
        highest,
        max(value + error for value, error in zip(overheads, upper_errors)),
    )
    color = VARIANT_COLORS[variant]
    ax.bar(
        xs,
        overheads[:-1],
        width=bar_width,
        yerr=np.array([lower_errors[:-1], upper_errors[:-1]]),
        label=VARIANT_LABELS[variant],
        color=color,
        edgecolor=darken_color(color),
        linewidth=BAR_EDGE_WIDTH,
        error_kw={
            "elinewidth": 0.65,
            "capthick": 0.65,
            "capsize": 1.4,
            "ecolor": "#333333",
        },
        zorder=3,
    )
    ax.bar(
        geomean_x,
        overheads[-1],
        width=geomean_bar_width,
        yerr=np.array([[lower_errors[-1]], [upper_errors[-1]]]),
        color=color,
        edgecolor=darken_color(color),
        linewidth=BAR_EDGE_WIDTH,
        error_kw={
            "elinewidth": 0.65,
            "capthick": 0.65,
            "capsize": 1.4,
            "ecolor": "#333333",
        },
        zorder=3,
    )
    geomean_annotations.append((geomean_x, overheads[-1]))

# Match the Speedometer GeoMean treatment: horizontal labels in staggered
# lanes, with elbow leaders identifying the corresponding narrow bars.
label_floor = max(
    max(value for _, value in geomean_annotations) * 1.15,
    highest * 0.64,
)
label_ceiling = highest * 0.96
label_levels = np.linspace(label_floor, label_ceiling, n_variants)
for (bar_x, value), label_y in zip(geomean_annotations, label_levels):
    ax.annotate(
        f"{value:.1f}%",
        xy=(bar_x, value),
        xytext=(bar_x - 0.10, label_y),
        ha="center",
        va="center",
        fontsize=FONT_SIZES["annotation"],
        fontweight="semibold",
        color="#222222",
        arrowprops={
            "arrowstyle": "-",
            "color": "#666666",
            "linewidth": 0.55,
            "shrinkA": 2,
            "shrinkB": 0,
            "connectionstyle": "angle,angleA=0,angleB=90,rad=0",
        },
        zorder=4,
    )

ax.axhline(0, color="#333333", linewidth=0.8, zorder=2)
lower_limit = max(1.0, np.ceil(abs(lowest) + 0.25))
upper_limit = max(4.0, np.ceil(highest + 0.75))
ax.set_ylim(-lower_limit, upper_limit)
ax.set_xlim(-0.55, x_group[-1] + BAR_GROUP_WIDTH / 2)
ax.set_xticks(x_group)
ax.set_xticklabels(
    [label for label, _ in ROWS],
    rotation=42,
    ha="right",
    rotation_mode="anchor",
)
ax.get_xticklabels()[-1].set_fontweight("bold")
ax.set_ylabel("Retired-instruction overhead (%)")
ax.grid(axis="x", visible=False)
ax.grid(axis="y", linestyle=":", color="#BBBBBB", linewidth=0.6)
ax.set_axisbelow(True)
ax.tick_params(axis="x", length=0, pad=3)
legend_handles, legend_labels = ax.get_legend_handles_labels()
legend_options = {
    "frameon": False,
    "loc": "upper center",
    "handlelength": 1.15,
    "handletextpad": 0.4,
    "columnspacing": 0.75,
    "labelspacing": 0.25,
    "borderaxespad": 0,
    "fontsize": FONT_SIZES["legend"],
}
if len(legend_handles) == 3:
    top_legend = ax.legend(
        legend_handles[:2],
        legend_labels[:2],
        bbox_to_anchor=(0.5, 1.16),
        ncol=2,
        **legend_options,
    )
    ax.add_artist(top_legend)
    ax.legend(
        legend_handles[2:],
        legend_labels[2:],
        bbox_to_anchor=(0.5, 1.07),
        ncol=1,
        **legend_options,
    )
else:
    ax.legend(
        legend_handles,
        legend_labels,
        bbox_to_anchor=(0.5, 1.16),
        ncol=min(2, n_variants),
        **legend_options,
    )

fig.subplots_adjust(left=0.18, right=0.99, top=0.86, bottom=0.29)
save_at_declared_size(fig, (Path(sys.argv[1]) / "instruction-overhead.pdf"))
