#!/usr/bin/env python3
"""Dot plot of performance retained relative to each engine's default."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import os

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
from figure_data import parse_data

PROJECT_DIR = Path(__file__).resolve().parents[3]
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

from common import run_scores, save_png_and_pdf, validate_records  # noqa: E402


SP3_AM = "speedometer-am"
SP3_ORACLE = "speedometer-am-oracle"
SP3_BASELINE = "speedometer-baseline"
SP3_DEFAULT = "speedometer-default"
SP3_V8_DEFAULT = "speedometer-v8-default"
SP3_V8_JITLESS = "speedometer-v8-jitless"
OCTANE_AM = "octane-am"
OCTANE_ORACLE = "octane-am-oracle"
OCTANE_BASELINE = "octane-baseline"
OCTANE_DEFAULT = "octane-default"
OCTANE_V8_DEFAULT = "octane-v8-default"
OCTANE_V8_JITLESS = "octane-v8-jitless"

CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")
SERIES = (
    ("AM", "aot-corpus"),
    ("AM-Oracle", "aot-oracle"),
    ("Baseline JIT", "default-no-ion"),
    ("V8 Jitless", "v8-jitless"),
)
WORKLOAD_MARKERS = {"Speedometer 3.1": "o", "Octane 2.0": "^"}


def retained(data, numerator, denominator):
    return 100.0 * np.mean(run_scores(data.columns[numerator])) / np.mean(
        run_scores(data.columns[denominator])
    )


apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
validate_records(
    data,
    (SP3_AM, SP3_ORACLE, SP3_BASELINE, SP3_DEFAULT),
    "Speedometer SpiderMonkey comparison",
)
validate_records(data, (SP3_V8_DEFAULT, SP3_V8_JITLESS), "Speedometer V8 comparison")
validate_records(
    data,
    (OCTANE_AM, OCTANE_ORACLE, OCTANE_BASELINE, OCTANE_DEFAULT),
    "Octane SpiderMonkey comparison",
)
validate_records(data, (OCTANE_V8_DEFAULT, OCTANE_V8_JITLESS), "Octane V8 comparison")

speedometer = (
    retained(data, SP3_AM, SP3_DEFAULT),
    retained(data, SP3_ORACLE, SP3_DEFAULT),
    retained(data, SP3_BASELINE, SP3_DEFAULT),
    retained(data, SP3_V8_JITLESS, SP3_V8_DEFAULT),
)
octane = (
    retained(data, OCTANE_AM, OCTANE_DEFAULT),
    retained(data, OCTANE_ORACLE, OCTANE_DEFAULT),
    retained(data, OCTANE_BASELINE, OCTANE_DEFAULT),
    retained(data, OCTANE_V8_JITLESS, OCTANE_V8_DEFAULT),
)

fig, ax = plt.subplots(figsize=figure_size("single", 2.58))
speedometer_label_positions = (
    (6, 0, "left", "center"),
    (-5, 7, "right", "bottom"),
    (-5, -7, "right", "top"),
    (6, 0, "left", "center"),
)
for y, ((label, slug), speedometer_value, octane_value, label_position) in enumerate(
    zip(SERIES, speedometer, octane, speedometer_label_positions)
):
    y = len(SERIES) - 1 - y
    color = CONFIGS[slug]["color"]
    ax.plot(
        (octane_value, speedometer_value),
        (y, y),
        color=color,
        linewidth=1.15,
        alpha=0.48,
        zorder=1,
    )
    ax.scatter(
        speedometer_value,
        y,
        marker=WORKLOAD_MARKERS["Speedometer 3.1"],
        s=47,
        color=color,
        edgecolor="white",
        linewidth=0.45,
        zorder=3,
    )
    ax.scatter(
        octane_value,
        y,
        marker=WORKLOAD_MARKERS["Octane 2.0"],
        s=51,
        color=color,
        edgecolor="white",
        linewidth=0.45,
        zorder=3,
    )
    ax.annotate(
        f"{octane_value:.1f}%",
        (octane_value, y),
        xytext=(0, 7),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=FONT_SIZES["annotation"],
        color="#333333",
    )
    dx, dy, horizontal_alignment, vertical_alignment = label_position
    ax.annotate(
        f"{label} {speedometer_value:.1f}%",
        (speedometer_value, y),
        xytext=(dx, dy),
        textcoords="offset points",
        ha=horizontal_alignment,
        va=vertical_alignment,
        fontsize=FONT_SIZES["annotation"],
        color="#333333",
    )

ax.axvline(100, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
ax.annotate(
    "100% (own default)",
    (100, 3.38),
    xytext=(-1, 2),
    textcoords="offset points",
    ha="right",
    va="bottom",
    fontsize=FONT_SIZES["annotation"],
    color="#444444",
)
ax.set_xlim(0, 102)
ax.set_ylim(-0.45, 3.5)
ax.set_xticks(np.arange(0, 101, 20), [f"{value}%" for value in range(0, 101, 20)])
ax.set_yticks([])
ax.grid(axis="x", color="#D8D8D8", linewidth=0.55, zorder=0)
for side in ("left", "right", "top"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#777777")
ax.spines["bottom"].set_linewidth(0.65)

workload_handles = [
    mlines.Line2D(
        [],
        [],
        linestyle="none",
        marker=marker,
        markersize=5.5,
        markerfacecolor="#777777",
        markeredgecolor="white",
        markeredgewidth=0.4,
        label=workload,
    )
    for workload, marker in WORKLOAD_MARKERS.items()
]
fig.legend(
    handles=workload_handles,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.02),
    ncol=2,
    frameon=False,
    handlelength=0.7,
    handletextpad=0.35,
    columnspacing=0.9,
    borderpad=0,
    fontsize=FONT_SIZES["legend"],
)
fig.subplots_adjust(left=0.07, right=0.96, bottom=0.20, top=0.88)
save_png_and_pdf(fig, (Path(sys.argv[1]) / "performance-retained-dots.pdf"))
