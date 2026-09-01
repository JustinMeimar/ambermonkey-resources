#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-subtest Speedometer 3 speedup for every variant, plus geomean."""

import math
import os
from pathlib import Path
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator
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
GEOMEAN_GROUP_WIDTH = 1.0  # wider bars in the geomean group to give it prominence

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
    "TodoMVC-JavaScript-ES6-Webpack-Complex-DOM": "JS ES6/Webpack",
    "TodoMVC-Lit-Complex-DOM": "Lit",
    "TodoMVC-Preact-Complex-DOM": "Preact",
    "TodoMVC-React-Complex-DOM": "React",
    "TodoMVC-React-Redux": "React/Redux",
    "TodoMVC-Svelte-Complex-DOM": "Svelte",
    "TodoMVC-Vue": "Vue",
    "TodoMVC-WebComponents": "Web Comp.",
    "TodoMVC-jQuery": "jQuery",
}


def geomean(values):
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


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
baseline_mean = {
    w: statistics.fmean(run_values(data.columns[NORMALIZE_TO], "workloads_ms", w))
    for w in workloads
}

# speedups[variant] = [per-workload speedups..., geomean]
speedups = {}
per_run_ratios = {}
for variant in variants:
    column = data.columns[variant]
    ratios = []
    per_run = []
    for w in workloads:
        runs = run_values(column, "workloads_ms", w)
        variant_mean = statistics.fmean(runs)
        ratios.append(baseline_mean[w] / variant_mean)
        per_run.append([baseline_mean[w] / r for r in runs])
    speedups[variant] = ratios + [geomean(ratios)]
    per_run_ratios[variant] = per_run

group_labels = [WORKLOAD_LABELS.get(w, w) for w in workloads] + ["Geomean"]
n_groups = len(group_labels)
n_variants = len(variants)
colors = [CONFIGS[v]["color"] for v in variants]
bar_width = GROUP_WIDTH / n_variants
geomean_bar_width = GEOMEAN_GROUP_WIDTH / n_variants
x = np.arange(n_groups)
geomean_idx = n_groups - 1

fig, ax = plt.subplots(figsize=figure_size("double", 1.68))

y_max = 0.0
for i, variant in enumerate(variants):
    workload_offset = (i - (n_variants - 1) / 2) * bar_width
    geomean_offset = (i - (n_variants - 1) / 2) * geomean_bar_width
    values = speedups[variant]
    workload_values = values[:-1]
    geomean_value = values[-1]
    err = [
        statistics.stdev(runs) if len(runs) > 1 else 0.0
        for runs in per_run_ratios[variant]
    ]
    ax.bar(
        x[:-1] + workload_offset,
        workload_values,
        bar_width * 0.94,
        yerr=err,
        color=colors[i],
        edgecolor="white",
        linewidth=0.25,
        error_kw={"elinewidth": 0.5, "capthick": 0.5, "capsize": 1.2, "ecolor": "#444"},
        label=CONFIGS[variant]["long"],
        zorder=3,
    )
    ax.bar(
        x[geomean_idx] + geomean_offset,
        geomean_value,
        geomean_bar_width * 0.94,
        color=colors[i],
        edgecolor="white",
        linewidth=0.25,
        zorder=3,
    )
    ax.text(
        x[geomean_idx] + geomean_offset,
        geomean_value * 1.05,
        f"{geomean_value:.1f}×",
        ha="center",
        va="bottom",
        rotation=90,
        fontsize=4.5,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.3},
        zorder=4,
    )
    y_max = max(y_max, max(v + e for v, e in zip(workload_values, err)), geomean_value)

ax.axhline(1.0, color="black", linewidth=0.6, linestyle="--", zorder=2)

ax.set_xticks(x)
ax.set_xticklabels(
    group_labels,
    rotation=65,
    ha="right",
    rotation_mode="anchor",
    fontsize=FONT_SIZES["annotation"],
)
ax.set_ylabel("Speedup over Interpreter")
ax.yaxis.set_major_locator(MultipleLocator(1))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}×"))
ax.set_xlim(-0.58, n_groups - 0.42)
ax.set_ylim(0, y_max * 1.10 if y_max else 1)
ax.grid(axis="x", visible=False)
ax.grid(axis="y", zorder=0)
ax.tick_params(axis="x", length=0, pad=2)
ax.margins(x=0.005)

ax.legend(
    frameon=False,
    loc="upper right",
    bbox_to_anchor=(1.0, 1.015),
    borderaxespad=0,
    ncol=n_variants,
    handlelength=1.1,
    handletextpad=0.4,
    columnspacing=1.4,
    fontsize=FONT_SIZES["annotation"],
)

fig.subplots_adjust(left=0.055, right=0.995, top=0.90, bottom=0.338)
save_png_and_pdf(fig, sys.argv[1])
