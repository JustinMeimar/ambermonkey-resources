#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Cycle differences from Baseline JIT for the indirection ablation."""

import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(
    os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3])
)
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
    save_at_declared_size,
)

from common import (  # noqa: E402
    BENCH_LABELS,
    CONFIG_FOR_VARIANT,
    metric_cells,
)


BASELINE = "baseline-jit"
VARIANTS = ("am-rit", "am-rit-nl", "am-rit-nl-vm")
BENCHES = (
    "stack-check",
    "vm-call",
    "abi-call",
    "prebarrier",
    "interrupt-check",
)
LEGEND_LABELS = {
    "am-rit": "RIT",
    "am-rit-nl": "+ Native-Linker",
    "am-rit-nl-vm": "+ Value Mirroring",
}
GROUP_HEIGHT = 0.72
FILL_ALPHA = 0.72
Z_95 = 1.96


def sample_count(table, variant, bench):
    return int(table[variant]["meta.retained_observations_per_benchmark"].mean)


apply_amber_style("single")
data = load_stdin()
cells = metric_cells(data, "cycles_per_iter")
table = data.flat_table()
configs = load_configurations()

n_variants = len(VARIANTS)
bar_height = GROUP_HEIGHT / n_variants
y_group = np.arange(len(BENCHES))[::-1]

fig, ax = plt.subplots(figsize=figure_size("single", 2.35))

leftmost = 0.0
rightmost = 0.0
for i, variant in enumerate(VARIANTS):
    offset = ((n_variants - 1) / 2 - i) * bar_height
    ys = y_group + offset
    overheads = []
    lower_errors = []
    upper_errors = []
    for bench in BENCHES:
        baseline = cells[bench][BASELINE]
        value = cells[bench][variant]
        baseline_n = sample_count(table, BASELINE, bench)
        value_n = sample_count(table, variant, bench)
        ratio = value.mean / baseline.mean
        overheads.append((ratio - 1.0) * 100.0)

        # A log-ratio interval stays valid on the positive ratio scale and
        # naturally allows asymmetric bounds after conversion to percentages.
        log_se = np.hypot(
            value.stddev / (np.sqrt(value_n) * value.mean),
            baseline.stddev / (np.sqrt(baseline_n) * baseline.mean),
        )
        lower_ratio = ratio * np.exp(-Z_95 * log_se)
        upper_ratio = ratio * np.exp(Z_95 * log_se)
        lower_errors.append((ratio - lower_ratio) * 100.0)
        upper_errors.append((upper_ratio - ratio) * 100.0)

    leftmost = min(
        leftmost,
        min(
            overhead - error
            for overhead, error in zip(overheads, lower_errors)
        ),
    )
    rightmost = max(
        rightmost,
        max(
            overhead + error
            for overhead, error in zip(overheads, upper_errors)
        ),
    )
    color = configs[CONFIG_FOR_VARIANT[variant]]["color"]
    ax.barh(
        ys,
        overheads,
        height=bar_height * 0.80,
        xerr=np.array([lower_errors, upper_errors]),
        label=LEGEND_LABELS[variant],
        color=color,
        alpha=FILL_ALPHA,
        edgecolor=color,
        linewidth=0.6,
        error_kw={
            "elinewidth": 0.65,
            "capthick": 0.65,
            "capsize": 1.4,
            "ecolor": "#333333",
        },
        zorder=3,
    )

# Baseline JIT is encoded as the reference, rather than as a fourth bar.
ax.axvline(0, color="#333333", linewidth=0.8, zorder=2)

left_limit = max(4.0, np.ceil(abs(leftmost) + 0.5))
right_limit = max(4.0, np.ceil(rightmost + 0.5))
ax.set_xlim(-left_limit, right_limit)
ax.set_yticks(y_group)
ax.set_yticklabels([BENCH_LABELS[bench] for bench in BENCHES])
ax.set_ylim(-0.55, len(BENCHES) - 0.45)
ax.set_xlabel("Cycle overhead vs. Baseline JIT (%, 95% CI)")
ax.grid(axis="x", linestyle=":", color="#BBBBBB", linewidth=0.6)
ax.grid(axis="y", visible=False)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0, pad=3)

ax.legend(
    frameon=False,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.17),
    ncol=3,
    handlelength=1.15,
    handletextpad=0.4,
    columnspacing=0.75,
    labelspacing=0.25,
    borderaxespad=0,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.24, right=0.98, top=0.84, bottom=0.21)
save_at_declared_size(fig, sys.argv[1])
