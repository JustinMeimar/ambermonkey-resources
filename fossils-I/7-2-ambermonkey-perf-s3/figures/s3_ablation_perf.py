#!/usr/bin/env python3
"""Aggregate Speedometer 3 speedup over interpreter-only."""

import math
import os
from pathlib import Path
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ["FOSSIL_PROJECT_DIR"])
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

from common import (  # noqa: E402
    child,
    run_values,
    save_png_and_pdf,
    validate_data,
)


NORMALIZE_TO = "interp-only"
CONFIGS = load_configurations()
VARIANT_ORDER = [
    slug for slug, _ in sorted(CONFIGS.items(), key=lambda item: item[1]["order"])
]
BAR_LABELS = {
    "interp-only": "Interpreter\nonly",
    "blinterp-only": "AM-∅",
    "aot-corpus-ic": "AM-IC",
    "aot-corpus": "AM",
    "default-no-ion": "Baseline\nJIT",
    "default": "Default\n(Ion)",
}


def geomean(values):
    return math.exp(math.fsum(math.log(value) for value in values) / len(values))


apply_amber_style("single")
data = load_stdin()
validate_data(data, baseline=NORMALIZE_TO)

extras = [variant for variant in data.column_names if variant not in VARIANT_ORDER]
if extras:
    raise ValueError(f"unexpected variants present: {extras}")

variants = [
    variant
    for variant in VARIANT_ORDER
    if variant in data.column_names
]

workloads = sorted(
    (child(data.columns[NORMALIZE_TO], "workloads_ms").children or {}).keys()
)
baseline_means = {
    workload: statistics.fmean(
        run_values(data.columns[NORMALIZE_TO], "workloads_ms", workload)
    )
    for workload in workloads
}

speedups = []
speedup_stdevs = []
for variant in variants:
    runs_by_workload = {
        workload: run_values(data.columns[variant], "workloads_ms", workload)
        for workload in workloads
    }
    run_counts = {len(runs) for runs in runs_by_workload.values()}
    if len(run_counts) != 1:
        raise ValueError(f"{variant}: inconsistent run counts across workloads")

    ratios = []
    for workload in workloads:
        variant_mean = statistics.fmean(runs_by_workload[workload])
        ratios.append(baseline_means[workload] / variant_mean)
    speedups.append(geomean(ratios))

    per_run_speedups = [
        geomean(
            [
                baseline_means[workload] / runs_by_workload[workload][run_index]
                for workload in workloads
            ]
        )
        for run_index in range(run_counts.pop())
    ]
    speedup_stdevs.append(
        statistics.stdev(per_run_speedups) if len(per_run_speedups) > 1 else 0.0
    )

n_variants = len(variants)
positions = list(range(n_variants))

fig, ax = plt.subplots(figsize=figure_size("single", 2.15))
for position, variant, speedup, speedup_stdev in zip(
    positions, variants, speedups, speedup_stdevs
):
    ax.bar(
        position,
        speedup,
        0.68,
        yerr=speedup_stdev if speedup_stdev else None,
        color=CONFIGS[variant]["color"],
        edgecolor="#555555",
        linewidth=0.4,
        error_kw={
            "ecolor": "#333333",
            "elinewidth": 0.8,
            "capthick": 0.8,
            "capsize": 2.5,
        },
        zorder=3,
    )
    ax.text(
        position,
        speedup + speedup_stdev + max(speedups) * 0.025,
        f"{speedup:.2f}",
        ha="center",
        va="bottom",
        fontsize=FONT_SIZES["annotation"],
    )

ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--", zorder=2)
ax.set_xticks(positions)
ax.set_xticklabels(
    [BAR_LABELS.get(variant, CONFIGS[variant]["short"]) for variant in variants]
)
ax.set_ylabel(f"Speedup over {CONFIGS[NORMALIZE_TO]['prose']}")
ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}×"))
ax.set_xlim(-0.62, n_variants - 0.38)
ax.set_ylim(
    0.0,
    max(speedup + stdev for speedup, stdev in zip(speedups, speedup_stdevs))
    * 1.14,
)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=4)

fig.subplots_adjust(left=0.19, right=0.985, top=0.94, bottom=0.27)
save_png_and_pdf(fig, sys.argv[1])
