#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Horizontal bar chart of AOT indirection overhead relative to the baseline variant."""

import math
import sys

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import apply_style, load_stdin


SCORE_METRIC = {
    "jetstream3":   "score",
    "speedometer3": "score",
}
WORKLOADS = ("jetstream3", "speedometer3")


def scalar(table, column, metric):
    entry = table.get(column, {}).get(metric)
    if entry is None:
        return None
    return entry.mean, entry.stddev


def ratio(num_mean, num_std, den_mean, den_std):
    if den_mean == 0:
        return 0.0, 0.0
    r = num_mean / den_mean
    rel = math.sqrt((num_std / num_mean) ** 2 + (den_std / den_mean) ** 2) if num_mean else 0.0
    return r, r * rel


apply_style(column="single")
data = load_stdin()
table = data.flat_table()

labels = []
means = []
errs = []
skipped = []
for workload in WORKLOADS:
    baseline_col = f"{workload}-baseline"
    aot_col = f"{workload}-aot-oracle"
    metric = SCORE_METRIC[workload]
    b = scalar(table, baseline_col, metric)
    a = scalar(table, aot_col, metric)
    if b is None or a is None:
        missing = [c for c, v in ((baseline_col, b), (aot_col, a)) if v is None]
        skipped.append((workload, missing))
        continue
    r, r_std = ratio(a[0], a[1], b[0], b[1])
    labels.append(workload)
    means.append(r)
    errs.append(r_std)

for workload, missing in skipped:
    print(f"overhead_bars: skipping {workload}; missing {missing}", file=sys.stderr)

if not labels:
    raise SystemExit("overhead_bars: no workload has both baseline and aot-oracle records")

fig, ax = plt.subplots(figsize=(6, 2 + 0.4 * len(labels)))
y = np.arange(len(labels))
ax.barh(y, means, xerr=errs, height=0.55, color="#4c72b0", edgecolor="none")
ax.axvline(1.0, color="#333", linewidth=0.8, linestyle="--")
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.set_xlabel("aot-oracle score / baseline score (higher is better)")
ax.set_title("AOT indirection overhead")
hi = max(m + e for m, e in zip(means, errs))
ax.set_xlim(0.0, max(1.05, hi * 1.05))
for i, (m, e) in enumerate(zip(means, errs)):
    ax.text(m + e + 0.01, y[i], f"{m:.3f} +/- {e:.3f}", va="center", fontsize=8)

fig.tight_layout()
fig.savefig(sys.argv[1])
