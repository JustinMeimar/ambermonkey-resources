#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer throughput for any set of variants, relative to interp-only."""

import math
import os
from pathlib import Path
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import get_colors, load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
)

from common import (
    run_values,
    save_png_and_pdf,
    scalar_at,
    validate_data,
)


NORMALIZE_TO = "interp-only"
DISPLAY_NAMES = {
    "interp-only": "IO",
    "aot-corpus": "AM",
    "default-no-ion": "BL",
    "default": "DEF",
}


def tick_step(x_max):
    for limit, step in ((2.0, 0.25), (4.0, 0.5), (8.0, 1.0)):
        if x_max <= limit:
            return step
    return 2.0


apply_amber_style("single")
data = load_stdin()
validate_data(data, baseline=NORMALIZE_TO)

baseline = run_values(data.columns[NORMALIZE_TO], "score")
baseline_score = statistics.fmean(baseline)
rows = []
for variant in data.column_names:
    values = run_values(data.columns[variant], "score")
    score = statistics.fmean(values)
    per_run_ratios = [v / baseline_score for v in values]
    ratio_std = statistics.stdev(per_run_ratios) if len(per_run_ratios) > 1 else 0.0
    rows.append((variant, score, score / baseline_score, len(values), ratio_std))

# Keep the normalization anchor first. Sort every other configuration by
# throughput so arbitrary variant names still produce a useful plot.
rows.sort(key=lambda row: (row[0] != NORMALIZE_TO, row[2], row[0]))
variants = [row[0] for row in rows]
scores = [row[1] for row in rows]
ratios = [row[2] for row in rows]
run_counts = [row[3] for row in rows]
ratio_errs = [row[4] for row in rows]
colors = get_colors(variants)

y_positions = np.arange(len(variants))
height = max(2.40, 1.50 + 0.22 * len(variants))
fig, (bar_ax, score_ax, delta_ax) = plt.subplots(
    1,
    3,
    figsize=figure_size("single", height),
    sharey=True,
    gridspec_kw={"width_ratios": [5.3, 1.20, 1.80]},
)

bar_ax.barh(
    y_positions,
    ratios,
    height=0.66,
    color=colors,
    edgecolor="none",
    xerr=ratio_errs,
    error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.5},
)
bar_ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")
bar_ax.set_yticks(y_positions)
bar_ax.set_yticklabels([DISPLAY_NAMES.get(variant, variant) for variant in variants])
bar_ax.invert_yaxis()
step = tick_step(max(ratios))
x_max = math.ceil(max(ratios) / step) * step
bar_ax.set_xlim(0.0, x_max)
bar_ax.set_xticks(np.arange(0.0, x_max + step / 2, step))
bar_ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}×"))
bar_ax.set_xlabel(f"Speedup over {NORMALIZE_TO}", labelpad=9)
bar_ax.grid(axis="y", visible=False)

for table_ax in (score_ax, delta_ax):
    table_ax.set_xlim(0.0, 1.0)
    table_ax.set_xticks([])
    table_ax.tick_params(axis="y", left=False, labelleft=False)
    table_ax.grid(False)
    for side in ("top", "right", "bottom"):
        table_ax.spines[side].set_visible(False)
    table_ax.spines["left"].set_color("#D8D8D8")
    table_ax.spines["left"].set_linewidth(0.8)

score_ax.set_title(
    "Score", fontsize=FONT_SIZES["annotation"], fontweight="bold", pad=4
)
delta_ax.set_title(
    "Change", fontsize=FONT_SIZES["annotation"], fontweight="bold", pad=4
)

for y, score, ratio, variant in zip(y_positions, scores, ratios, variants):
    score_ax.text(
        0.5,
        y,
        f"{score:.2f}",
        ha="center",
        va="center",
        fontsize=FONT_SIZES["annotation"],
    )
    change = "0.0%" if variant == NORMALIZE_TO else f"{(ratio - 1.0) * 100:+.1f}%"
    delta_ax.text(
        0.5,
        y,
        change,
        ha="center",
        va="center",
        fontsize=FONT_SIZES["annotation"],
    )

page_cycles = {
    int(scalar_at(data.columns[variant], "meta", "page_cycles"))
    for variant in variants
}
if len(set(run_counts)) == 1:
    noun = "run" if run_counts[0] == 1 else "runs"
    run_note = f"n={run_counts[0]} browser {noun} per variant"
else:
    run_note = f"n={min(run_counts)}–{max(run_counts)} browser runs per variant"
if len(page_cycles) == 1:
    cycle_note = f"{next(iter(page_cycles))} page cycles per run"
else:
    cycle_note = (
        f"{min(page_cycles)}–{max(page_cycles)} page cycles per run "
        "across variants"
    )
fig.text(
    0.5,
    0.008,
    f"Ratios of browser-run means; {run_note}; {cycle_note}.",
    ha="center",
    va="bottom",
    fontsize=FONT_SIZES["note"],
)
fig.subplots_adjust(
    left=0.15,
    right=0.995,
    bottom=0.27,
    top=0.92,
    wspace=0.06,
)
save_png_and_pdf(fig, sys.argv[1])
