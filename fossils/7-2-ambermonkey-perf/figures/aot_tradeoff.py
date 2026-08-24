#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-workload cost of AOT indirection and recovery over interpreter-only."""

import os
from pathlib import Path
import statistics
import sys

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    AMBER_BLUE,
    AMBER_RED,
    FONT_SIZES,
    apply_amber_style,
    figure_size,
)

from common import (
    child,
    run_values,
    save_png_and_pdf,
    validate_data,
)


def pretty_workload(name):
    replacements = {
        "Charts-chartjs": "Charts: Chart.js",
        "Charts-observable-plot": "Charts: Observable Plot",
        "Editor-CodeMirror": "Editor: CodeMirror",
        "Editor-TipTap": "Editor: TipTap",
        "NewsSite-Next": "News: Next",
        "NewsSite-Nuxt": "News: Nuxt",
        "Perf-Dashboard": "Perf Dashboard",
        "React-Stockcharts-SVG": "React Stockcharts (SVG)",
        "TodoMVC-Angular-Complex-DOM": "Angular (complex DOM)",
        "TodoMVC-Backbone": "Backbone",
        "TodoMVC-JavaScript-ES5": "JavaScript ES5",
        "TodoMVC-JavaScript-ES6-Webpack-Complex-DOM": (
            "JavaScript ES6/Webpack"
        ),
        "TodoMVC-Lit-Complex-DOM": "Lit (complex DOM)",
        "TodoMVC-Preact-Complex-DOM": "Preact (complex DOM)",
        "TodoMVC-React-Complex-DOM": "React (complex DOM)",
        "TodoMVC-React-Redux": "React/Redux",
        "TodoMVC-Svelte-Complex-DOM": "Svelte (complex DOM)",
        "TodoMVC-Vue": "Vue",
        "TodoMVC-WebComponents": "Web Components",
        "TodoMVC-jQuery": "jQuery",
    }
    return replacements.get(name, name)


apply_amber_style("double")
data = load_stdin()
validate_data(data)

AOT = "aot-interp-ics-baseline"
RUNTIME = "interp-ics-baseline"
INTERP_ONLY = "interp-only"

workloads = sorted((child(data.columns[AOT], "workloads_ms").children or {}).keys())
effects = []
n_runs = None
for workload in workloads:
    aot = run_values(data.columns[AOT], "workloads_ms", workload)
    runtime = run_values(data.columns[RUNTIME], "workloads_ms", workload)
    interp_only = run_values(data.columns[INTERP_ONLY], "workloads_ms", workload)
    if n_runs is None:
        n_runs = min(len(aot), len(runtime), len(interp_only))

    cost = statistics.mean(aot) / statistics.mean(runtime)
    recovery = statistics.mean(interp_only) / statistics.mean(aot)
    effects.append((workload, cost, recovery))

# Put the largest observed position-independence costs first.
effects.sort(key=lambda item: item[1], reverse=True)
slower_count = sum(cost > 1.0 for _, cost, _ in effects)

fig, (cost_ax, recovery_ax) = plt.subplots(
    1,
    2,
    figsize=figure_size("double", 6.0),
    sharey=True,
    gridspec_kw={"width_ratios": [1.08, 0.92]},
)
y_positions = np.arange(len(effects))

for y, (_, cost, recovery) in zip(y_positions, effects):
    cost_change = (cost - 1.0) * 100.0
    cost_color = AMBER_RED if cost_change > 0.0 else AMBER_BLUE
    cost_ax.plot(
        cost_change,
        y,
        "o",
        markersize=3.3,
        color=cost_color,
    )

    recovery_ax.plot(
        recovery,
        y,
        "o",
        markersize=3.3,
        color=AMBER_BLUE,
    )

labels = [pretty_workload(workload) for workload, _, _ in effects]
cost_ax.set_yticks(y_positions)
cost_ax.set_yticklabels(labels, fontsize=FONT_SIZES["note"])
cost_ax.invert_yaxis()

cost_ax.axvline(0.0, color="black", linewidth=0.8)
cost_ax.set_xlabel("Execution-time change (%)")
cost_ax.set_title("(a) AOT cost vs. runtime codegen", pad=17)
cost_ax.grid(axis="y", visible=False)
cost_ax.text(
    0.5,
    1.005,
    f"{slower_count}/{len(effects)} workloads slower",
    transform=cost_ax.transAxes,
    ha="center",
    va="bottom",
    fontsize=FONT_SIZES["note"],
)

recovery_ax.axvline(1.0, color="black", linewidth=0.8)
recovery_ax.set_xscale("log")
recovery_ax.xaxis.set_major_locator(FixedLocator([1.0, 1.5, 2.0, 3.0, 4.0]))
recovery_ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}×"))
recovery_ax.set_xlabel("Speedup over interpreter only")
recovery_ax.set_title("(b) AOT recovery", pad=17)
recovery_ax.grid(axis="y", visible=False)
recovery_ax.tick_params(axis="y", left=False, labelleft=False)
recovery_ax.spines["left"].set_visible(False)

fig.text(
    0.995,
    0.008,
    f"Ratios of browser-run means (n={n_runs}/configuration).",
    ha="right",
    va="bottom",
    fontsize=FONT_SIZES["note"],
)
fig.subplots_adjust(
    left=0.30,
    right=0.985,
    bottom=0.10,
    top=0.94,
    wspace=0.16,
)

save_png_and_pdf(fig, sys.argv[1])
