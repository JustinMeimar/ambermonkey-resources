#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer 3 headroom recovered from each engine's default: horizontal bars.

Each bar is that configuration's score as a percentage of its own engine's
default (which by definition is 100%, so we omit the reference bars).
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    BAR_EDGE_WIDTH,
    FONT_SIZES,
    apply_amber_style,
    darken_color,
    figure_size,
    load_configurations,
)
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402

from common import (
    load_oracle_speedometer,
    run_scores,
    save_png_and_pdf,
    validate_records,
)


SM_DEFAULT = "default"
SM_INTERP = "interp-only"
SM_AM = "aot-corpus"
SM_ORACLE = "aot-oracle"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"
CONFIGS = load_configurations()


def sm_bar(data, variant, default_scores, rng):
    scores = run_scores(data.columns[variant])
    if len(scores) >= 2 and len(default_scores) >= 2:
        ratio, lower_error, upper_error = bootstrap_ratio_ci(
            scores, default_scores, rng
        )
    else:
        ratio = np.mean(scores) / np.mean(default_scores)
        lower_error = upper_error = 0.0
    return {
        "slug": variant,
        "ratio": ratio,
        "lower_error": lower_error,
        "upper_error": upper_error,
        "n": len(scores),
    }


def label_for(slug):
    if slug == SM_ORACLE:
        return "AM-Oracle"
    long = CONFIGS[slug]["long"]
    return long


def oracle_bar(rng):
    scores = load_oracle_speedometer()
    oracle_scores = scores["speedometer3-aot-only"]
    oracle_default = scores["speedometer3-default"]
    if len(oracle_scores) >= 2 and len(oracle_default) >= 2:
        ratio, lower_error, upper_error = bootstrap_ratio_ci(
            oracle_scores, oracle_default, rng
        )
    else:
        ratio = np.mean(oracle_scores) / np.mean(oracle_default)
        lower_error = upper_error = 0.0
    return {
        "slug": SM_ORACLE,
        "ratio": ratio,
        "lower_error": lower_error,
        "upper_error": upper_error,
        "n": len(oracle_scores),
    }


apply_amber_style("single")

data = load_stdin()
validate_records(
    data,
    (SM_INTERP, SM_AM, SM_DEFAULT, V8_DEFAULT, V8_JITLESS),
    "comparison",
)

sm_default = run_scores(data.columns[SM_DEFAULT])
v8_default = run_scores(data.columns[V8_DEFAULT])
rng = np.random.default_rng(0)

# Top-to-bottom: V8 Jitless, the oracle corpus, AmberMonkey, interpreter.
bars = [
    sm_bar(data, V8_JITLESS, v8_default, rng),
    oracle_bar(rng),
    sm_bar(data, SM_AM, sm_default, rng),
    sm_bar(data, SM_INTERP, sm_default, rng),
]

BAR_HEIGHT = 0.16
BAR_GAP = 0.025
TOP_PAD = 0.14
BOTTOM_PAD = 0.14

# Layout, top-to-bottom (larger y is drawn higher), with a narrow visual gap.
bar_bottoms = [
    (len(bars) - index - 1) * (BAR_HEIGHT + BAR_GAP)
    for index in range(len(bars))
]
positions_for_bars = [b + BAR_HEIGHT / 2 for b in bar_bottoms]
top_y = bar_bottoms[0] + BAR_HEIGHT

ratios = [b["ratio"] for b in bars]
lower_errors = [b["lower_error"] for b in bars]
upper_errors = [b["upper_error"] for b in bars]
# Amber tones identify the SpiderMonkey configurations; hatched blues identify
# the V8 configurations.
bar_colors = {
    V8_JITLESS: "#4393C3",
    SM_ORACLE: "#B35806",
    SM_AM: "#E08214",
    SM_INTERP: "#FDD49E",
}
colors = [bar_colors[b["slug"]] for b in bars]
labels = [label_for(b["slug"]) for b in bars]
hatches = ["///" if b["slug"] == V8_JITLESS else "" for b in bars]

height = 1.38
fig, ax = plt.subplots(figsize=figure_size("single", height))

bar_handles = ax.barh(
    positions_for_bars,
    ratios,
    height=BAR_HEIGHT,
    color=colors,
    edgecolor=[darken_color(color) for color in colors],
    linewidth=BAR_EDGE_WIDTH,
    xerr=np.array([lower_errors, upper_errors]),
    error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.0},
    label=None,
)
# Give each bar its own legend entry (matplotlib groups a single `barh` call).
for patch, label, hatch in zip(bar_handles.patches, labels, hatches):
    patch.set_label(label)
    patch.set_hatch(hatch)

ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")

ax.set_yticks([])
ax.set_ylim(-BOTTOM_PAD, top_y + TOP_PAD)

x_max = 1.10
ax.set_xlim(0.0, x_max)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
ax.set_xlabel("Speedometer 3.1 score (% of engine default)")
ax.grid(axis="x", visible=True, linestyle=":", color="#BBBBBB", linewidth=0.6)
ax.set_axisbelow(True)

# Score annotations sit at the right end of each bar.
score_pad = x_max * 0.012
for yi, bar in zip(positions_for_bars, bars):
    text = "TODO" if bar["ratio"] == 0.0 else f"{bar['ratio'] * 100:.1f}%"
    ax.text(
        bar["ratio"] + bar["upper_error"] + score_pad, yi, text,
        ha="left", va="center",
        fontsize=FONT_SIZES["annotation"],
    )

ax.legend(
    loc="lower center",
    bbox_to_anchor=(0.5, 1.02),
    ncol=len(bars),
    frameon=False,
    handlelength=1.1,
    handleheight=0.9,
    handletextpad=0.4,
    columnspacing=0.8,
    borderpad=0.0,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.04, right=0.98, bottom=0.28, top=0.78)
save_png_and_pdf(fig, sys.argv[1])
