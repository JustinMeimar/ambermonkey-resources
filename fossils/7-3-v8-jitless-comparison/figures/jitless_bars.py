#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer 3 headroom recovered from each engine's default: three bars."""

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
    return {
        "slug": variant,
        "score": mean,
        "score_stdev": stdev,
        "ratio": ratio,
        "ratio_err": ratio_err,
        "n": n,
    }


def v8_bar(v8, slug, default_score):
    entry = v8["columns"][slug]
    mean, stdev, n = summarize(entry.get("samples", []), entry.get("score", 0.0))
    ratio = mean / default_score if default_score else 0.0
    ratio_err = stdev / default_score if default_score else 0.0
    return {
        "slug": slug,
        "score": mean,
        "score_stdev": stdev,
        "ratio": ratio,
        "ratio_err": ratio_err,
        "n": n,
    }


apply_amber_style("single")

data = load_stdin()
validate_sm(data, (SM_INTERP, SM_AM, SM_DEFAULT))
v8 = load_v8()

sm_default = summarize(run_scores(data.columns[SM_DEFAULT]), fallback_score=0.0)[0]
v8_default = summarize(
    v8["columns"][V8_DEFAULT].get("samples", []),
    v8["columns"][V8_DEFAULT].get("score", 0.0),
)[0]

bars = [
    v8_bar(v8, V8_JITLESS, v8_default),
    sm_bar(data, SM_INTERP, sm_default),
    sm_bar(data, SM_AM, sm_default),
]
# Draw top-to-bottom: V8 first, then the SM pair (worst SM, then recovered SM).

def label_for(slug):
    long = CONFIGS[slug]["long"]
    if slug in (SM_INTERP, SM_AM) and not long.lower().startswith("spidermonkey"):
        return f"SM {long}"
    return long


labels = [label_for(b["slug"]) for b in bars]
ratios = [b["ratio"] for b in bars]
errs = [b["ratio_err"] for b in bars]
colors = [CONFIGS[b["slug"]]["color"] for b in bars]

y = np.arange(len(bars))
height = max(2.20, 1.10 + 0.42 * len(bars))
fig, ax = plt.subplots(figsize=figure_size("single", height))

ax.barh(
    y, ratios, height=0.60, color=colors, edgecolor="none",
    xerr=errs, error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.5},
)
ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.invert_yaxis()

x_max = max(1.05, max(ratios) * 1.10 if any(r > 0 for r in ratios) else 1.05)
ax.set_xlim(0.0, x_max)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
ax.set_xlabel("Score as % of engine's default")
ax.grid(axis="y", visible=False)

label_pad = x_max * 0.015
for yi, bar in zip(y, bars):
    text = "TODO" if bar["ratio"] == 0.0 else f"{bar['ratio'] * 100:.1f}%"
    ax.text(
        bar["ratio"] + bar["ratio_err"] + label_pad, yi, text,
        va="center", ha="left",
        fontsize=FONT_SIZES["annotation"],
    )

sm_n = min(b["n"] for b in bars if b["slug"] != V8_JITLESS)
v8_n = bars[0]["n"]
note = f"SpiderMonkey n={sm_n} browser runs; V8 n={v8_n or 'TODO'} (manual)."
fig.text(0.5, 0.008, note, ha="center", va="bottom", fontsize=FONT_SIZES["note"])

fig.subplots_adjust(left=0.30, right=0.97, bottom=0.28, top=0.94)
save_png_and_pdf(fig, sys.argv[1])
