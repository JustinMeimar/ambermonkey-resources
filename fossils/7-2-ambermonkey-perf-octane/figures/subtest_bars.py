#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-subtest Octane speedup for restricted variants, plus geomean."""

import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullLocator
import numpy as np
from fossil_figures import FigureData, load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    BAR_EDGE_WIDTH,
    BAR_GROUP_WIDTH,
    FONT_SIZES,
    GEOMEAN_GROUP_GAP,
    apply_amber_style,
    darken_color,
    figure_size,
    load_configurations,
)
from benchmark_stats import (  # noqa: E402
    bootstrap_geomean_ratio_ci,
    bootstrap_ratio_ci,
)

from common import (  # noqa: E402
    child,
    run_values,
    save_png_and_pdf,
    validate_data,
)


NORMALIZE_TO = "interp-only"
PLOT_VARIANTS = ("blinterp-only", "aot-corpus-ic", "aot-corpus", "aot-oracle")
CONFIGS = load_configurations()
VARIANT_ORDER = [slug for slug, _ in sorted(CONFIGS.items(), key=lambda kv: kv[1]["order"])]

# Octane emits mostly camel-case single-word workload names; keep the map
# open-ended so the figure still renders if new subtests appear.
WORKLOAD_LABELS = {
    "EarleyBoyer": "Earley-Boyer",
    "NavierStokes": "Navier-Stokes",
    "RegExp": "RegExp",
    "SplayLatency": "Splay Lat.",
    "MandreelLatency": "Mandreel Lat.",
    "PdfJS": "PDF.js",
    "GbEmulator": "Gameboy",
    "CodeLoad": "Code-Load",
    "Box2D": "Box2D",
    "Typescript": "TypeScript",
}


def ratio_ci(numerator, denominator, rng):
    if len(numerator) < 2 or len(denominator) < 2:
        return np.mean(numerator) / np.mean(denominator), 0.0, 0.0
    return bootstrap_ratio_ci(numerator, denominator, rng)


def geomean_ratio_ci(numerator, denominator, rng):
    if len(numerator) < 2 or len(denominator) < 2:
        ratios = np.mean(numerator, axis=0) / np.mean(denominator, axis=0)
        return float(np.exp(np.mean(np.log(ratios)))), 0.0, 0.0
    return bootstrap_geomean_ratio_ci(numerator, denominator, rng)


apply_amber_style("double")
data = load_stdin()
extras = [v for v in data.column_names if v not in VARIANT_ORDER]
if extras:
    raise ValueError(f"unexpected variants present: {extras}")
variants = [v for v in PLOT_VARIANTS if v in data.column_names]
if not variants:
    raise ValueError(f"no plotted variants present; expected a subset of {PLOT_VARIANTS}")
data = FigureData(
    {v: data.columns[v] for v in (NORMALIZE_TO, *variants) if v in data.columns}
)
validate_data(data, baseline=NORMALIZE_TO)

workloads = sorted((child(data.columns[NORMALIZE_TO], "workload_scores").children or {}).keys())
baseline_runs = {
    w: run_values(data.columns[NORMALIZE_TO], "workload_scores", w)
    for w in workloads
}

speedups = {}
errors = {}
rng = np.random.default_rng(0)
for variant in variants:
    column = data.columns[variant]
    results = []
    variant_runs = {}
    for w in workloads:
        variant_runs[w] = run_values(column, "workload_scores", w)
        results.append(ratio_ci(variant_runs[w], baseline_runs[w], rng))
    aggregate = geomean_ratio_ci(
        np.array([variant_runs[w] for w in workloads]).T,
        np.array([baseline_runs[w] for w in workloads]).T,
        rng,
    )
    results.append(aggregate)
    speedups[variant] = [result[0] for result in results]
    errors[variant] = (
        [result[1] for result in results],
        [result[2] for result in results],
    )

group_labels = [WORKLOAD_LABELS.get(w, w) for w in workloads] + ["Geomean"]
n_groups = len(group_labels)
n_variants = len(variants)
colors = [CONFIGS[v]["color"] for v in variants]
bar_width = BAR_GROUP_WIDTH / n_variants
geomean_bar_width = bar_width
x = np.arange(n_groups, dtype=float)
geomean_idx = n_groups - 1
x[geomean_idx] += GEOMEAN_GROUP_GAP

fig, ax = plt.subplots(figsize=figure_size("double", 1.35))

geomean_annotations = []
y_max = 1.0
for i, variant in enumerate(variants):
    workload_offset = (i - (n_variants - 1) / 2) * bar_width
    geomean_offset = (i - (n_variants - 1) / 2) * geomean_bar_width
    values = speedups[variant]
    workload_values = values[:-1]
    geomean_value = values[-1]
    lower_errors, upper_errors = errors[variant]
    ax.bar(
        x[:-1] + workload_offset,
        workload_values,
        bar_width,
        yerr=np.array([lower_errors[:-1], upper_errors[:-1]]),
        color=colors[i],
        edgecolor=darken_color(colors[i]),
        linewidth=BAR_EDGE_WIDTH,
        error_kw={"elinewidth": 0.5, "capthick": 0.5, "capsize": 1.2, "ecolor": "#444"},
        label=("AM-Oracle*" if variant == "aot-oracle" else CONFIGS[variant]["long"]),
        zorder=3,
    )
    ax.bar(
        x[geomean_idx] + geomean_offset,
        geomean_value,
        geomean_bar_width,
        yerr=np.array([[lower_errors[-1]], [upper_errors[-1]]]),
        color=colors[i],
        edgecolor=darken_color(colors[i]),
        linewidth=BAR_EDGE_WIDTH,
        error_kw={"elinewidth": 0.5, "capthick": 0.5, "capsize": 1.2, "ecolor": "#444"},
        zorder=3,
    )
    geomean_annotations.append(
        (x[geomean_idx] + geomean_offset, geomean_value, upper_errors[-1])
    )
    y_max = max(y_max, max(v + e for v, e in zip(values, upper_errors)))

# Label each GeoMean bar directly; vertical text fits the narrow bars without
# leaders or extra horizontal space.
axis_ceiling = max(10.0, y_max * 1.12)
for bar_x, value, upper_error in geomean_annotations:
    ax.text(
        bar_x,
        (value + upper_error) * 1.10,
        f"{value:.1f}×",
        ha="center",
        va="bottom",
        rotation=90,
        fontsize=FONT_SIZES["annotation"] - 0.5,
        fontweight="semibold",
        color="#222222",
        zorder=4,
    )
ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--", zorder=2)

ax.set_xticks(x)
ax.set_xticklabels(
    group_labels,
    rotation=52,
    ha="right",
    rotation_mode="anchor",
    fontsize=FONT_SIZES["annotation"],
)
ax.set_ylabel("Speedup over Interp")
ax.set_yscale("log")
# Show 1×, 2×, 5×, 10×, 20×, 50×, ... as major ticks on the log axis;
# the default LogLocator only labels decades, which reads as "1×, 10×"
# and hides most of the variation.
ax.yaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0, 2.0, 5.0), numticks=12))
ax.yaxis.set_minor_locator(NullLocator())
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
ax.set_xlim(-0.55, x[geomean_idx] + BAR_GROUP_WIDTH / 2)
y_min_pos = 0.1
ax.set_ylim(y_min_pos, axis_ceiling)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=2)
ax.margins(x=0.005)

fig.subplots_adjust(left=0.075, right=0.995, top=0.975, bottom=0.35)
save_png_and_pdf(fig, sys.argv[1])
