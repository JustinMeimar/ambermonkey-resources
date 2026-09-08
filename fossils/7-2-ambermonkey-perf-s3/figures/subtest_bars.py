#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-subtest Speedometer 3 speedup for every variant, plus geomean."""

import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
from fossil_figures import load_stdin

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

from common import (
    child,
    run_values,
    save_png_and_pdf,
    validate_data,
)


NORMALIZE_TO = "interp-only"
CONFIGS = load_configurations()
VARIANT_ORDER = [slug for slug, _ in sorted(CONFIGS.items(), key=lambda kv: kv[1]["order"])]

WORKLOAD_LABELS = {
    "Charts-chartjs": "Chart.js",
    "Charts-observable-plot": "Observable",
    "Editor-CodeMirror": "CodeMirror",
    "Editor-TipTap": "TipTap",
    "NewsSite-Next": "Next",
    "NewsSite-Nuxt": "Nuxt",
    "Perf-Dashboard": "Perf Dash",
    "React-Stockcharts-SVG": "Stockcharts",
    "TodoMVC-Angular-Complex-DOM": "Angular",
    "TodoMVC-Backbone": "Backbone",
    "TodoMVC-JavaScript-ES5": "JS ES5",
    "TodoMVC-JavaScript-ES6-Webpack-Complex-DOM": "WP-ES6",
    "TodoMVC-Lit-Complex-DOM": "Lit",
    "TodoMVC-Preact-Complex-DOM": "Preact",
    "TodoMVC-React-Complex-DOM": "React",
    "TodoMVC-React-Redux": "React/Redux",
    "TodoMVC-Svelte-Complex-DOM": "Svelte",
    "TodoMVC-Vue": "Vue",
    "TodoMVC-WebComponents": "Web Comp.",
    "TodoMVC-jQuery": "jQuery",
}


apply_amber_style("double")
data = load_stdin()
validate_data(data, baseline=NORMALIZE_TO)

variants = [v for v in VARIANT_ORDER if v in data.column_names and v != NORMALIZE_TO]
# The registry can list configurations not measured by this fossil; only
# error on data-side variants that the registry doesn't know about.
extras = [v for v in data.column_names if v not in VARIANT_ORDER]
if extras:
    raise ValueError(f"unexpected variants present: {extras}")

workloads = sorted((child(data.columns[NORMALIZE_TO], "workloads_ms").children or {}).keys())
baseline_runs = {
    w: run_values(data.columns[NORMALIZE_TO], "workloads_ms", w)
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
        variant_runs[w] = run_values(column, "workloads_ms", w)
        results.append(bootstrap_ratio_ci(baseline_runs[w], variant_runs[w], rng))
    aggregate = bootstrap_geomean_ratio_ci(
        np.array([baseline_runs[w] for w in workloads]).T,
        np.array([variant_runs[w] for w in workloads]).T,
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

fig, ax = plt.subplots(figsize=figure_size("double", 1.82))

y_max = 0.0
geomean_annotations = []
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
        label=CONFIGS[variant]["long"],
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
        (x[geomean_idx] + geomean_offset, geomean_value)
    )
    y_max = max(
        y_max,
        max(v + e for v, e in zip(values, upper_errors)),
    )

# Place larger horizontal labels in staggered lanes and connect each one to
# its narrow Geo Mean bar. This uses the otherwise empty headroom without
# requiring tiny vertical type.
label_floor = max(max(value for _, value in geomean_annotations) * 1.15, y_max * 0.64)
label_ceiling = y_max * 0.96
label_levels = np.linspace(label_floor, label_ceiling, n_variants)
for (bar_x, value), label_y in zip(geomean_annotations, label_levels):
    ax.annotate(
        f"{value:.1f}×",
        xy=(bar_x, value),
        xytext=(bar_x - 0.10, label_y),
        ha="center",
        va="center",
        fontsize=FONT_SIZES["annotation"],
        fontweight="semibold",
        color="#222222",
        arrowprops={
            "arrowstyle": "-",
            "color": "#666666",
            "linewidth": 0.55,
            "shrinkA": 2,
            "shrinkB": 0,
            "connectionstyle": "angle,angleA=0,angleB=90,rad=0",
        },
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
ax.set_ylabel("Speedup over Interpreter")
ax.yaxis.set_major_locator(MultipleLocator(1))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
ax.set_xlim(-0.55, x[geomean_idx] + BAR_GROUP_WIDTH / 2)
ax.set_ylim(0, y_max * 1.05 if y_max else 1)
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
    fontsize=FONT_SIZES["annotation"],
)

fig.subplots_adjust(left=0.055, right=0.995, top=0.90, bottom=0.315)
save_png_and_pdf(fig, sys.argv[1])
