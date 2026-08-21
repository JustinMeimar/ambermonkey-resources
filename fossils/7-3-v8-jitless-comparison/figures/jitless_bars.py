#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer 3 headroom recovered from each engine's default: horizontal bars.

Each bar is that configuration's score as a percentage of its own engine's
default (which by definition is 100%, so we omit the reference bars). The two
SpiderMonkey bars touch to visually bind them as one family; V8 --jitless
sits above with a gap.
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

from common import (
    load_v8,
    run_scores,
    save_png_and_pdf,
    summarize,
    summarize_column,
    validate_sm,
)


SM_DEFAULT = "default"
SM_INTERP = "interp-only"
SM_AM = "aot-corpus"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"
CONFIGS = load_configurations()


def sm_bar(data, variant, default_score):
    scores = run_scores(data.columns[variant])
    mean, stdev, n = summarize(scores, fallback_score=0.0)
    ratio = mean / default_score if default_score else 0.0
    ratio_err = stdev / default_score if default_score else 0.0
    return {"slug": variant, "ratio": ratio, "ratio_err": ratio_err, "n": n}


def v8_bar(v8, slug, default_score):
    mean, stdev, n = summarize_column(v8["columns"][slug])
    ratio = mean / default_score if default_score else 0.0
    ratio_err = stdev / default_score if default_score else 0.0
    return {"slug": slug, "ratio": ratio, "ratio_err": ratio_err, "n": n}


def label_for(slug):
    long = CONFIGS[slug]["long"]
    if slug in (SM_INTERP, SM_AM) and not long.lower().startswith("spidermonkey"):
        return f"SM {long}"
    return long


apply_amber_style("single")

data = load_stdin()
validate_sm(data, (SM_INTERP, SM_AM, SM_DEFAULT))
v8 = load_v8()

sm_default = summarize(run_scores(data.columns[SM_DEFAULT]), fallback_score=0.0)[0]
v8_default = summarize_column(v8["columns"][V8_DEFAULT])[0]

# Top-to-bottom: V8 --jitless (separated), then the two SM bars touching.
bars = [
    v8_bar(v8, V8_JITLESS, v8_default),
    sm_bar(data, SM_INTERP, sm_default),
    sm_bar(data, SM_AM, sm_default),
]

BAR_HEIGHT = 0.55
GROUP_GAP = 0.80         # extra space between the V8 slot and the SM pair
TOP_PAD = 0.38
BOTTOM_PAD = 0.38

# Softer fills + engine-level hatch. Colors still identify each variant; the
# hatch distinguishes V8 from the SM family at a glance even in grayscale.
FILL_ALPHA = 0.45
HATCH_BY_ENGINE = {V8_JITLESS: "//"}

# Layout, top-to-bottom (larger y is drawn higher):
#   [V8 --jitless bar]
#   ---- GROUP_GAP ----
#   [SM Interpreter only bar]   <-- touches next bar
#   [SM AmberMonkey bar]
y_am_bar = 0.0
y_interp_bar = y_am_bar + BAR_HEIGHT                           # touches AM bar top
y_v8_bar = y_interp_bar + BAR_HEIGHT + GROUP_GAP

bar_bottoms = [y_v8_bar, y_interp_bar, y_am_bar]               # order matches `bars`
positions_for_bars = [b + BAR_HEIGHT / 2 for b in bar_bottoms]
top_y = y_v8_bar + BAR_HEIGHT

ratios = [b["ratio"] for b in bars]
errs = [b["ratio_err"] for b in bars]
colors = [CONFIGS[b["slug"]]["color"] for b in bars]
labels = [label_for(b["slug"]) for b in bars]

height = 1.60
fig, ax = plt.subplots(figsize=figure_size("single", height))

# Hatch lines need to survive Typst's scale-down of the embedded PDF; a
# thinner stroke rounds to sub-pixel and disappears at print resolution.
plt.rcParams["hatch.linewidth"] = 1.4
face_colors = [to_rgba(c, FILL_ALPHA) for c in colors]

bar_handles = ax.barh(
    positions_for_bars, ratios, height=BAR_HEIGHT, color=face_colors,
    edgecolor=colors, linewidth=0.9,
    xerr=errs, error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.0},
    label=None,
)
# Give each bar its own legend entry (matplotlib groups a single `barh` call)
# and apply the per-engine hatch. Hatch inherits the patch edge color.
for patch, label, bar in zip(bar_handles.patches, labels, bars):
    patch.set_label(label)
    hatch = HATCH_BY_ENGINE.get(bar["slug"])
    if hatch:
        patch.set_hatch(hatch)

ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")

ax.set_yticks([])
ax.set_ylim(-BOTTOM_PAD, top_y + TOP_PAD)

x_max = 1.10
ax.set_xlim(0.0, x_max)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
ax.set_xlabel("Score as % of engine's default")
ax.grid(axis="x", visible=True, linestyle=":", color="#BBBBBB", linewidth=0.6)
ax.set_axisbelow(True)

# Score annotations sit at the right end of each bar.
score_pad = x_max * 0.012
for yi, bar in zip(positions_for_bars, bars):
    text = "TODO" if bar["ratio"] == 0.0 else f"{bar['ratio'] * 100:.1f}%"
    ax.text(
        bar["ratio"] + bar["ratio_err"] + score_pad, yi, text,
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
    columnspacing=1.0,
    borderpad=0.0,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.04, right=0.98, bottom=0.24, top=0.82)
save_png_and_pdf(fig, sys.argv[1])
