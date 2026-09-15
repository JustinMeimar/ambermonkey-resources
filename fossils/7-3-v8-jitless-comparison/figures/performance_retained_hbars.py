#!/usr/bin/env python3
"""Compact horizontal bars for performance retained by workload."""

import os
from pathlib import Path
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_hex, to_rgb
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ["FOSSIL_PROJECT_DIR"])
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    darken_color,
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

CONFIGS = load_configurations()
SERIES = (
    ("AmberMonkey (SM)", "aot-corpus"),
    ("AmberMonkey-Oracle (SM)", "aot-oracle"),
    ("Baseline JIT (SM)", "default-no-ion"),
    ("JITless (V8)", "v8-jitless"),
)
LOCAL_FONT_SCALE = 1.08


def lighten_color(color, amount=0.18):
    """Blend a color toward white while preserving its configuration hue."""
    return to_hex(
        tuple(channel + (1.0 - channel) * amount for channel in to_rgb(color))
    )


def retained(data, numerator, denominator, rng):
    ratio, lower_error, upper_error = bootstrap_ratio_ci(
        run_scores(data.columns[numerator]),
        run_scores(data.columns[denominator]),
        rng,
    )
    return tuple(100.0 * value for value in (ratio, lower_error, upper_error))


apply_amber_style("single")
data = load_stdin()
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

rng = np.random.default_rng(0)
speedometer = (
    retained(data, SP3_AM, SP3_DEFAULT, rng),
    retained(data, SP3_ORACLE, SP3_DEFAULT, rng),
    retained(data, SP3_BASELINE, SP3_DEFAULT, rng),
    retained(data, SP3_V8_JITLESS, SP3_V8_DEFAULT, rng),
)
octane = (
    retained(data, OCTANE_AM, OCTANE_DEFAULT, rng),
    retained(data, OCTANE_ORACLE, OCTANE_DEFAULT, rng),
    retained(data, OCTANE_BASELINE, OCTANE_DEFAULT, rng),
    retained(data, OCTANE_V8_JITLESS, OCTANE_V8_DEFAULT, rng),
)

fig, ax = plt.subplots(figsize=figure_size("single", 1.92))
centers = np.arange(len(SERIES))[::-1]
centers[-1] -= 0.03
bar_height = 0.268
pair_gap = 0.025
offset = (bar_height + pair_gap) / 2

for center, (label, slug), speedometer_result, octane_result in zip(
    centers, SERIES, speedometer, octane
):
    color = CONFIGS[slug]["color"]
    edgecolor = darken_color(color)
    for (value, lower_error, upper_error), y, hatch, facecolor in (
        (speedometer_result, center + offset, "", color),
        (octane_result, center - offset, "////", lighten_color(color)),
    ):
        ax.barh(
            y,
            value,
            height=bar_height,
            color=facecolor,
            edgecolor=edgecolor,
            linewidth=0.55,
            hatch=hatch,
            xerr=np.array([[lower_error], [upper_error]]),
            error_kw={
                "ecolor": "#222222",
                "elinewidth": 0.75,
                "capsize": 2.0,
                "capthick": 0.75,
            },
            zorder=2,
        )
        ax.text(
            value + upper_error + 0.6,
            y,
            f"{value:.1f}%",
            ha="left",
            va="center",
            fontsize=FONT_SIZES["annotation"] * LOCAL_FONT_SCALE,
            fontweight="semibold",
            color="#333333",
        )
    ax.text(
        1.0,
        center + 0.31,
        label,
        ha="left",
        va="bottom",
        fontsize=FONT_SIZES["annotation"] * LOCAL_FONT_SCALE,
        color="#222222",
    )

ax.axvline(100, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
ax.set_xlim(0, 106)
ax.set_ylim(-0.48, len(SERIES) - 0.52)
ax.set_xticks(np.arange(0, 101, 20), [f"{value}%" for value in range(0, 101, 20)])
ax.tick_params(axis="x", labelsize=FONT_SIZES["tick"] * LOCAL_FONT_SCALE)
ax.set_yticks([])
ax.grid(axis="x", color="#D8D8D8", linewidth=0.55, zorder=0)
ax.grid(False, axis="y")
for side in ("right", "top"):
    ax.spines[side].set_visible(False)
ax.spines["left"].set_color("#222222")
ax.spines["left"].set_linewidth(0.8)
ax.spines["bottom"].set_color("#777777")
ax.spines["bottom"].set_linewidth(0.65)

legend_color = "#E6E6E6"
legend_octane_color = lighten_color(legend_color, amount=0.45)
legend_edgecolor = "#666666"
handles = (
    mpatches.Patch(
        facecolor=legend_color,
        edgecolor=legend_edgecolor,
        linewidth=0.55,
        label="Speedometer 3.1",
    ),
    mpatches.Patch(
        facecolor=legend_octane_color,
        edgecolor=legend_edgecolor,
        linewidth=0.55,
        hatch="////",
        label="Octane 2.0",
    ),
)
fig.legend(
    handles=handles,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.015),
    ncol=2,
    frameon=False,
    handlelength=1.1,
    handleheight=0.7,
    handletextpad=0.4,
    columnspacing=0.9,
    borderpad=0,
    fontsize=FONT_SIZES["legend"] * LOCAL_FONT_SCALE,
)
fig.subplots_adjust(left=0.08, right=0.98, bottom=0.25, top=0.96)
save_png_and_pdf(fig, sys.argv[1])
