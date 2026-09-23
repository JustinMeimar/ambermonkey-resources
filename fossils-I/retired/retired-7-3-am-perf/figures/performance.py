#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Held-out suite throughput, normalized to each interpreter-only control."""

import math
from pathlib import Path
import statistics
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import apply_style, load_stdin


WORKLOADS = ("speedometer3", "jetstream3")
WORKLOAD_LABELS = {
    "speedometer3": "Speedometer 3",
    "jetstream3": "JetStream 3",
}
POLICIES = ("interp-only", "am-strict", "default")
POLICY_LABELS = {
    "interp-only": "Interpreter only",
    "am-strict": "AmberMonkey strict",
    "default": "Default JIT",
}
COLORS = {
    "interp-only": "#7A7A7A",
    "am-strict": "#2E86AB",
    "default": "#D1495B",
}
T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def child(metric, key):
    if metric.children is None or key not in metric.children:
        raise ValueError(f"missing metric path component {key!r}")
    return metric.children[key]


def tag_at(metric, *path):
    for key in path:
        metric = child(metric, key)
    if metric.tag is None:
        raise ValueError(f"metric {'.'.join(path)!r} is not a tag")
    return metric.tag


def run_scores(column):
    runs = child(column, "runs")
    if not runs.children:
        raise ValueError("analysis contains no independent browser runs")
    values = []
    for run_name in sorted(runs.children):
        score = child(runs.children[run_name], "score")
        if score.scalar is None:
            raise ValueError(f"{run_name}.score is not scalar")
        values.append(score.scalar.mean)
    return values


def t_critical(df):
    if df < 1:
        raise ValueError("at least two independent samples are required")
    return T95.get(df, 1.96)


def ratio_ci(numerator, denominator):
    if len(numerator) < 2 or len(denominator) < 2:
        raise ValueError("at least two runs per policy are required for a CI")
    if any(value <= 0 for value in numerator + denominator):
        raise ValueError("suite scores must be positive")
    ratio = statistics.mean(numerator) / statistics.mean(denominator)
    log_num = [math.log(value) for value in numerator]
    log_den = [math.log(value) for value in denominator]
    se = math.sqrt(
        statistics.variance(log_num) / len(log_num)
        + statistics.variance(log_den) / len(log_den)
    )
    half_width = t_critical(min(len(log_num), len(log_den)) - 1) * se
    center = math.log(ratio)
    return ratio, math.exp(center - half_width), math.exp(center + half_width)


def baseline_ci(values):
    if len(values) < 2:
        raise ValueError("at least two interpreter-only runs are required")
    logs = [math.log(value) for value in values]
    half_width = (
        t_critical(len(logs) - 1)
        * statistics.stdev(logs)
        / math.sqrt(len(logs))
    )
    return 1.0, math.exp(-half_width), math.exp(half_width)


apply_style(column="double")
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
data = load_stdin()

expected = {
    f"{workload}-{policy}" for workload in WORKLOADS for policy in POLICIES
}
found = set(data.column_names)
if found != expected:
    raise ValueError(
        f"expected variants {sorted(expected)}, missing {sorted(expected - found)}, "
        f"unexpected {sorted(found - expected)}"
    )

commits = {
    tag_at(data.columns[variant], "meta", "commit") for variant in sorted(expected)
}
if len(commits) != 1 or "" in commits:
    raise ValueError(f"variants do not share one valid source commit: {commits}")

fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.85), sharey=True)
all_highs = []
n_values = set()
for ax, workload in zip(axes, WORKLOADS):
    baseline = run_scores(data.columns[f"{workload}-interp-only"])
    n_values.add(len(baseline))
    points = []
    for policy in POLICIES:
        variant = f"{workload}-{policy}"
        column = data.columns[variant]
        if tag_at(column, "meta", "workload") != workload:
            raise ValueError(f"{variant}: analysis workload tag disagrees")
        if tag_at(column, "meta", "policy") != policy:
            raise ValueError(f"{variant}: analysis policy tag disagrees")
        values = run_scores(column)
        n_values.add(len(values))
        estimate = (
            baseline_ci(values)
            if policy == "interp-only"
            else ratio_ci(values, baseline)
        )
        points.append(estimate)

    means = [point[0] for point in points]
    lows = [point[1] for point in points]
    highs = [point[2] for point in points]
    all_highs.extend(highs)
    y = np.arange(len(POLICIES))
    ax.barh(
        y,
        means,
        height=0.64,
        color=[COLORS[policy] for policy in POLICIES],
        edgecolor="none",
        xerr=[
            [mean - low for mean, low in zip(means, lows)],
            [high - mean for mean, high in zip(means, highs)],
        ],
        error_kw={"ecolor": "black", "elinewidth": 1.0, "capsize": 2.5},
    )
    ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title(WORKLOAD_LABELS[workload], fontsize=10, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([POLICY_LABELS[policy] for policy in POLICIES])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}x"))

x_max = max(all_highs) * 1.05
for ax in axes:
    ax.set_xlim(0.0, x_max)
axes[0].set_ylabel("Execution policy")
fig.supxlabel("Suite score relative to interpreter only (higher is better)", y=0.10)

if len(n_values) == 1:
    sample_note = f"n={next(iter(n_values))} independent browser runs per policy"
else:
    sample_note = f"n={min(n_values)}-{max(n_values)} independent browser runs per policy"
fig.text(
    0.995,
    0.018,
    f"Ratio of browser-run means; log-space 95% t intervals; {sample_note}.",
    ha="right",
    va="bottom",
    fontsize=6.5,
)
fig.subplots_adjust(left=0.25, right=0.99, bottom=0.29, top=0.87, wspace=0.12)

output = Path(sys.argv[1])
with mpl.rc_context({"savefig.bbox": None}):
    fig.savefig(output)
    fig.savefig(output.with_suffix(".pdf"))
