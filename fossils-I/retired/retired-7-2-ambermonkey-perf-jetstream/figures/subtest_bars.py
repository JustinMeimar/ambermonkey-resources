#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-benchmark JetStream 3 speedup for every variant, plus geomean.

Structural mirror of the Speedometer subtest_bars figure. JetStream 3
scores are higher-is-better, so the per-benchmark ratio is
variant_score / baseline_score rather than baseline_ms / variant_ms.
"""

import math
import os
from pathlib import Path
import statistics
import sys

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
    child,
    run_values,
    save_png_and_pdf,
    validate_data,
)


NORMALIZE_TO = "interp-only"
CONFIGS = load_configurations()
VARIANT_ORDER = [slug for slug, _ in sorted(CONFIGS.items(), key=lambda kv: kv[1]["order"])]
GROUP_WIDTH = 0.82


def short_label(name: str) -> str:
    """Compact tick label with only lossless substitutions.

    Suffixes like ``-wasm`` are load-bearing: ``richards`` and
    ``richards-wasm`` are distinct benchmarks that would collide if
    stripped. Only apply prefix/infix contractions that stay unique
    across the JetStream 3 subtest set.
    """
    return (
        name.replace("stanford-crypto-", "sc-")
            .replace("-inspector", "-insp")
    )


def geomean(values):
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


apply_amber_style("double")
data = load_stdin()
validate_data(data, baseline=NORMALIZE_TO)

variants = [v for v in VARIANT_ORDER if v in data.column_names and v != NORMALIZE_TO]
extras = [v for v in data.column_names if v not in VARIANT_ORDER]
if extras:
    raise ValueError(f"unexpected variants present: {extras}")

subtests = sorted((child(data.columns[NORMALIZE_TO], "subtests").children or {}).keys())
baseline_mean = {
    s: statistics.fmean(run_values(data.columns[NORMALIZE_TO], "subtests", s))
    for s in subtests
}

# speedups[variant] = [per-benchmark speedups..., geomean]
speedups = {}
per_run_ratios = {}
for variant in variants:
    column = data.columns[variant]
    ratios = []
    per_run = []
    for s in subtests:
        runs = run_values(column, "subtests", s)
        variant_mean = statistics.fmean(runs)
        ratios.append(variant_mean / baseline_mean[s])
        per_run.append([r / baseline_mean[s] for r in runs])
    speedups[variant] = ratios + [geomean(ratios)]
    per_run_ratios[variant] = per_run

group_labels = [short_label(s) for s in subtests] + ["Geomean"]
n_groups = len(group_labels)
n_variants = len(variants)
colors = [CONFIGS[v]["color"] for v in variants]
bar_width = GROUP_WIDTH / n_variants
x = np.arange(n_groups)

# Width scales linearly with the number of benchmark groups so per-group bar
# width stays consistent whether the fossil ships 20 or 80 benchmarks. The
# 0.09 in/group heuristic yields a ~7 in figure at 77 benchmarks + geomean.
inches_per_group = 0.09
fig_width = max(7.0, inches_per_group * n_groups + 0.5)
fig, ax = plt.subplots(figsize=(fig_width, 2.55))

y_max = 0.0
for i, variant in enumerate(variants):
    offset = (i - (n_variants - 1) / 2) * bar_width
    values = speedups[variant]
    err = [
        statistics.stdev(runs) if len(runs) > 1 else 0.0
        for runs in per_run_ratios[variant]
    ] + [0.0]
    ax.bar(
        x + offset,
        values,
        bar_width * 0.94,
        yerr=err,
        color=colors[i],
        edgecolor="white",
        linewidth=0.25,
        error_kw={"elinewidth": 0.5, "capthick": 0.5, "capsize": 1.2, "ecolor": "#444"},
        label=CONFIGS[variant]["long"],
        zorder=3,
    )
    y_max = max(y_max, max(v + e for v, e in zip(values, err)))

ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--", zorder=2)
ax.axvline(n_groups - 1.5, color="#B8B8B8", linewidth=0.7, linestyle=":", zorder=1)

# Tick font scales down mildly at larger N so labels do not overplot.
tick_fs = FONT_SIZES["tick"] if n_groups <= 30 else max(4.2, FONT_SIZES["tick"] - 0.06 * (n_groups - 30))
ax.set_xticks(x)
ax.set_xticklabels(
    group_labels,
    rotation=68,
    ha="right",
    rotation_mode="anchor",
    fontsize=tick_fs,
)
ax.set_ylabel(f"Speedup over {CONFIGS[NORMALIZE_TO]['prose']}")
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
ax.set_xlim(-0.58, n_groups - 0.42)
ax.set_ylim(0, y_max * 1.10 if y_max else 1)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=2)
ax.margins(x=0.005)

ax.legend(
    frameon=False,
    loc="upper left",
    bbox_to_anchor=(0.0, 1.015),
    borderaxespad=0,
    ncol=n_variants,
    handlelength=1.1,
    handletextpad=0.4,
    columnspacing=1.4,
)

# Wider label rotations at bigger N need proportionally more bottom margin.
bottom = 0.27 if n_groups <= 25 else min(0.42, 0.27 + 0.003 * (n_groups - 25))
fig.subplots_adjust(left=0.04, right=0.997, top=0.92, bottom=bottom)
save_png_and_pdf(fig, sys.argv[1])
