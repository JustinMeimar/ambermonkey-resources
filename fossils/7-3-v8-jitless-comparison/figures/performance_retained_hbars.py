#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Compact horizontal bars for performance retained by workload."""

import os
from pathlib import Path
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
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
SP3_ORACLE_DEFAULT = "speedometer-oracle-default"
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


def retained(data, numerator, denominator):
    return 100.0 * np.mean(run_scores(data.columns[numerator])) / np.mean(
        run_scores(data.columns[denominator])
    )


apply_amber_style("single")
data = load_stdin()
validate_records(data, (SP3_AM, SP3_BASELINE, SP3_DEFAULT), "Speedometer SpiderMonkey comparison")
validate_records(data, (SP3_ORACLE, SP3_ORACLE_DEFAULT), "Speedometer oracle comparison")
validate_records(data, (SP3_V8_DEFAULT, SP3_V8_JITLESS), "Speedometer V8 comparison")
validate_records(
    data,
    (OCTANE_AM, OCTANE_ORACLE, OCTANE_BASELINE, OCTANE_DEFAULT),
    "Octane SpiderMonkey comparison",
)
validate_records(data, (OCTANE_V8_DEFAULT, OCTANE_V8_JITLESS), "Octane V8 comparison")

speedometer = (
    retained(data, SP3_AM, SP3_DEFAULT),
    retained(data, SP3_ORACLE, SP3_ORACLE_DEFAULT),
    retained(data, SP3_BASELINE, SP3_DEFAULT),
    retained(data, SP3_V8_JITLESS, SP3_V8_DEFAULT),
)
octane = (
    retained(data, OCTANE_AM, OCTANE_DEFAULT),
    retained(data, OCTANE_ORACLE, OCTANE_DEFAULT),
    retained(data, OCTANE_BASELINE, OCTANE_DEFAULT),
    retained(data, OCTANE_V8_JITLESS, OCTANE_V8_DEFAULT),
)

fig, ax = plt.subplots(figsize=figure_size("single", 1.92))
centers = np.arange(len(SERIES))[::-1]
centers[-1] -= 0.03
bar_height = 0.268
offset = bar_height / 2

for center, (label, slug), speedometer_value, octane_value in zip(
    centers, SERIES, speedometer, octane
):
    color = CONFIGS[slug]["color"]
    edgecolor = darken_color(color)
    for value, y, hatch in (
        (speedometer_value, center + offset, ""),
        (octane_value, center - offset, "////"),
    ):
        ax.barh(
            y,
            value,
            height=bar_height,
            color=color,
            edgecolor=edgecolor,
            linewidth=0.55,
            hatch=hatch,
            zorder=2,
        )
        ax.text(
            value + 1.1,
            y,
            f"{value:.1f}%",
            ha="left",
            va="center",
            fontsize=FONT_SIZES["annotation"],
            fontweight="semibold",
            color="#333333",
        )
    ax.text(
        1.0,
        center + 0.31,
        label,
        ha="left",
        va="bottom",
        fontsize=FONT_SIZES["annotation"],
        color="#222222",
    )

ax.axvline(100, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
ax.set_xlim(0, 112)
ax.set_ylim(-0.48, len(SERIES) - 0.52)
ax.set_xticks(np.arange(0, 101, 20), [f"{value}%" for value in range(0, 101, 20)])
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
legend_edgecolor = "#666666"
handles = (
    mpatches.Patch(
        facecolor=legend_color,
        edgecolor=legend_edgecolor,
        linewidth=0.55,
        label="Speedometer 3.1",
    ),
    mpatches.Patch(
        facecolor=legend_color,
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
    fontsize=FONT_SIZES["legend"],
)
fig.subplots_adjust(left=0.08, right=0.98, bottom=0.25, top=0.96)
save_png_and_pdf(fig, sys.argv[1])
