#!/home/justin/tools/fossil/figures/.venv/bin/python
"""One-column grouped bars for the Baseline AOT indirection ablation."""

import math
import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    AMBER_BLUE,
    AMBER_PURPLE,
    AMBER_RED,
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    save_at_declared_size,
)


BUILDS = ("default", "opt", "no-opt")
PLOT_BUILDS = ("default", "opt")
BENCHES = (
    "interrupt-check",
    "stack-check",
    "prebarrier",
    "vm-call",
    "abi-call",
    "arith",
    "prop-load",
    "array-load",
)
LABELS = {
    "interrupt-check": "interrupt",
    "stack-check": "stack",
    "prebarrier": "pre-barrier",
    "vm-call": "VM call",
    "abi-call": "ABI call",
    "arith": "arithmetic",
    "prop-load": "property",
    "array-load": "array",
}
LEGEND_LABELS = {
    "default": "Runtime",
    "opt": "AOT",
    "no-opt": "AOT, no opts",
}
COLORS = {
    "default": AMBER_BLUE,
    "opt": AMBER_RED,
    "no-opt": AMBER_PURPLE,
}
METRIC = "cycles_per_iter"
GROUP_WIDTH = 0.78


def split_variant(variant):
    # Match no-opt before opt: the former contains the latter as a suffix.
    for build in sorted(BUILDS, key=len, reverse=True):
        suffix = "-" + build
        if variant.endswith(suffix):
            return variant[: -len(suffix)], build
    return None, None


def scalar(table, column, metric):
    entry = table.get(column, {}).get(metric)
    if entry is None:
        return None
    return entry.mean, entry.stddev


def geometric_mean(values):
    if not values or any(value <= 0 for value in values):
        return None
    return math.exp(math.fsum(math.log(value) for value in values) / len(values))


apply_amber_style("single")
data = load_stdin()
table = data.flat_table()

# cells[bench][build] = (mean, stddev)
cells = {}
for variant in table:
    bench, build = split_variant(variant)
    if bench is None:
        continue
    value = scalar(table, variant, METRIC)
    if value is not None:
        cells.setdefault(bench, {})[build] = value

if not cells:
    raise SystemExit("cycles_bars: no <bench>-<build> variants with cycles_per_iter")

benches = [bench for bench in BENCHES if bench in cells]
benches += sorted(set(cells) - set(benches))
present_builds = [
    build for build in PLOT_BUILDS if any(build in cells[b] for b in benches)
]
n_builds = len(present_builds)
bar_width = GROUP_WIDTH / n_builds
x = np.arange(len(benches))

fig, ax = plt.subplots(figsize=figure_size("single", 2.58))

highest = 0.0
for i, build in enumerate(present_builds):
    offset = (i - (n_builds - 1) / 2) * bar_width
    xs, means, stddevs = [], [], []
    for j, bench in enumerate(benches):
        value = cells[bench].get(build)
        if value is None:
            continue
        xs.append(x[j] + offset)
        means.append(value[0])
        stddevs.append(value[1])
        highest = max(highest, value[0] + value[1])

    bars = ax.bar(
        xs,
        means,
        bar_width * 0.92,
        yerr=stddevs,
        label=LEGEND_LABELS[build],
        color=COLORS[build],
        edgecolor="white",
        linewidth=0.35,
        error_kw={"elinewidth": 0.7, "capthick": 0.7, "capsize": 1.8},
        zorder=3,
    )
    ax.bar_label(
        bars,
        labels=[f"{mean:.1f}" for mean in means],
        padding=2,
        rotation=90,
        fontsize=FONT_SIZES["annotation"],
    )

# The aggregate is the geometric mean of per-benchmark ratios, not a ratio
# formed by arithmetically averaging heterogeneous cycles/iteration values.
ratios = []
for bench in benches:
    runtime = cells[bench].get("default")
    aot = cells[bench].get("opt")
    if runtime is not None and aot is not None and runtime[0] > 0:
        ratios.append(aot[0] / runtime[0])
gmean = geometric_mean(ratios)

ax.set_xticks(x)
ax.set_xticklabels(
    [LABELS.get(bench, bench) for bench in benches],
    rotation=52,
    ha="right",
    rotation_mode="anchor",
)
ax.set_ylabel("user cycles / iteration")
ax.set_xlim(-0.58, len(benches) - 0.42)
ax.set_ylim(0, highest * 1.24 if highest else 1)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=3)
ax.margins(x=0.01)

if len(benches) > 5:
    ax.axvline(4.5, color="#B8B8B8", linewidth=0.7, linestyle=":", zorder=1)

if n_builds > 1:
    ax.legend(
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(-0.01, 1.015),
        borderaxespad=0,
        handlelength=1.2,
        labelspacing=0.25,
    )

if gmean is not None:
    ax.text(
        0.99,
        0.985,
        f"GM = {gmean:.2f}×",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=FONT_SIZES["tick"],
        fontweight="bold",
        color=COLORS["opt"],
    )

fig.subplots_adjust(left=0.17, right=0.995, top=0.96, bottom=0.16)
save_at_declared_size(fig, sys.argv[1])
