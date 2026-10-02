#!/usr/bin/env python3
"""Grouped user-cycle bars for the AmberMonkey indirection ablation."""

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
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
    save_at_declared_size,
)

from common import (  # noqa: E402
    BENCHES,
    BENCH_LABELS,
    CONFIG_FOR_VARIANT,
    VARIANTS,
    VARIANT_LABELS,
    metric_cells,
)


GROUP_WIDTH = 0.82


apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
cells = metric_cells(data, "cycles_per_iter")
configs = load_configurations(PROJECT_DIR / "configurations.toml")
colors = {
    variant: configs[CONFIG_FOR_VARIANT[variant]]["color"] for variant in VARIANTS
}

n_variants = len(VARIANTS)
bar_width = GROUP_WIDTH / n_variants
x = np.arange(len(BENCHES))

fig, ax = plt.subplots(figsize=figure_size("single", 2.65))

highest = 0.0
for i, variant in enumerate(VARIANTS):
    offset = (i - (n_variants - 1) / 2) * bar_width
    means = [cells[bench][variant].mean for bench in BENCHES]
    stddevs = [cells[bench][variant].stddev for bench in BENCHES]
    highest = max(
        highest,
        max(mean + stddev for mean, stddev in zip(means, stddevs)),
    )
    ax.bar(
        x + offset,
        means,
        bar_width * 0.92,
        yerr=stddevs,
        label=VARIANT_LABELS[variant],
        color=colors[variant],
        edgecolor="white",
        linewidth=0.35,
        error_kw={"elinewidth": 0.7, "capthick": 0.7, "capsize": 1.5},
        zorder=3,
    )

ax.set_xticks(x)
ax.set_xticklabels(
    [BENCH_LABELS[bench] for bench in BENCHES],
    rotation=42,
    ha="right",
    rotation_mode="anchor",
)
ax.set_ylabel("User cycles / iteration")
ax.set_xlim(-0.58, len(BENCHES) - 0.42)
ax.set_ylim(0, highest * 1.08 if highest else 1)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=3)
ax.legend(
    frameon=False,
    loc="upper left",
    bbox_to_anchor=(-0.01, 1.02),
    borderaxespad=0,
    handlelength=1.2,
    labelspacing=0.25,
    ncol=2,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.17, right=0.995, top=0.82, bottom=0.19)
save_at_declared_size(fig, (Path(sys.argv[1]) / "cycles-bars.pdf"))
