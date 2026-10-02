"""Shared one-column horizontal layout for performance-retention panels."""

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

from figure_style import (
    BAR_EDGE_WIDTH,
    FONT_SIZES,
    darken_color,
    figure_size,
)


def draw_reclamation_bars(ax, bars, xlabel, *, legend=True):
    """Draw one panel of ratios relative to each configuration's engine default."""
    bar_height = 0.15
    bar_gap = 0.018
    top_pad = 0.12
    bottom_pad = 0.12

    bottoms = [
        (len(bars) - index - 1) * (bar_height + bar_gap)
        for index in range(len(bars))
    ]
    positions = [bottom + bar_height / 2 for bottom in bottoms]
    top_y = bottoms[0] + bar_height

    ratios = [bar["ratio"] for bar in bars]
    lower_errors = [bar["lower_error"] for bar in bars]
    upper_errors = [bar["upper_error"] for bar in bars]
    colors = [bar["color"] for bar in bars]

    handles = ax.barh(
        positions,
        ratios,
        height=bar_height,
        color=colors,
        edgecolor=[darken_color(color) for color in colors],
        linewidth=BAR_EDGE_WIDTH,
        xerr=np.array([lower_errors, upper_errors]),
        error_kw={"ecolor": "#333333", "elinewidth": 0.8, "capsize": 2.0},
        zorder=3,
    )
    for patch, bar in zip(handles.patches, bars):
        patch.set_label(bar["label"])
        if bar.get("hatch"):
            patch.set_hatch(bar["hatch"])

    ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--", zorder=2)
    ax.set_yticks([])
    ax.set_ylim(-bottom_pad, top_y + top_pad)
    ax.set_xlim(0.0, 1.10)
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: f"{value * 100:.0f}%")
    )
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", linestyle=":", color="#BBBBBB", linewidth=0.6, zorder=0)

    for position, bar in zip(positions, bars):
        ax.text(
            bar["ratio"] + bar["upper_error"] + 0.012,
            position,
            f"{bar['ratio'] * 100:.1f}%",
            ha="left",
            va="center",
            fontsize=FONT_SIZES["annotation"],
        )

    if legend:
        ax.legend(
            loc="lower center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=3 if len(bars) > 4 else len(bars),
            frameon=False,
            handlelength=1.0,
            handleheight=0.8,
            handletextpad=0.35,
            columnspacing=0.65,
            borderpad=0.0,
            fontsize=FONT_SIZES["legend"],
        )

    return handles


def render_reclamation_bars(bars, xlabel, save, output_path):
    """Render one standalone retained-performance panel."""
    height = 1.52 if len(bars) > 4 else 1.38
    fig, ax = plt.subplots(figsize=figure_size("single", height))
    draw_reclamation_bars(ax, bars, xlabel)

    fig.subplots_adjust(
        left=0.055,
        right=0.98,
        bottom=0.27 if len(bars) > 4 else 0.28,
        top=0.72 if len(bars) > 4 else 0.78,
    )
    save(fig, output_path)
