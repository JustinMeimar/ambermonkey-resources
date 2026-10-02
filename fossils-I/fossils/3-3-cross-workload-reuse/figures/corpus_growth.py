#!/usr/bin/env python3
"""Four cumulative tp6-Test intersection curves over tp6-Train prefixes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import json
from collections import Counter

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, PercentFormatter
from figure_style import apply_amber_style
from figure_data import parse_data

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from corpus_growth import (  # noqa: E402
    ASCENDING_IC_SIZE_TRAIN_ORDER,
    intersection_curve,
)
from pairwise import split_sites  # noqa: E402


def tag(metric, key):
    if not metric.children or key not in metric.children:
        return ""
    return (metric.children[key].tag or "").strip()


def decode_set(metric, key):
    encoded = tag(metric, key)
    return set(encoded.split(",")) if encoded else set()


def decode_counter(metric, key):
    values = Counter()
    encoded = tag(metric, key)
    if encoded:
        for entry in encoded.split(";"):
            identity, count = entry.rsplit("=", 1)
            values[identity] = int(count)
    return values


apply_amber_style(column="single")
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

data = parse_data(json.load(sys.stdin))
train_sites, test_sites = split_sites()
all_sites = tuple(sorted(train_sites)) + test_sites
missing = [site for site in all_sites if site not in data.columns]
if missing:
    sys.exit(f"corpus-growth: missing workload records: {', '.join(missing)}")

ic_sets = {}
ic_frequencies = {}
baseline_sets = {}
baseline_frequencies = {}
for site in all_sites:
    metric = data.columns[site]
    ic_sets[site] = decode_set(metric, "ic_hashes")
    ic_frequencies[site] = decode_counter(metric, "ic_freqs")
    baseline_sets[site] = decode_set(metric, "baseline_hashes")
    baseline_frequencies[site] = decode_counter(metric, "baseline_freqs")
    if not all(
        (
            ic_sets[site],
            ic_frequencies[site],
            baseline_sets[site],
            baseline_frequencies[site],
        )
    ):
        sys.exit(f"corpus-growth: incomplete metrics for {site}")

# Order training sites by ascending IC-body count; break ties on
# alphabetical slug so the curve is deterministic.
train_sites = tuple(sorted(train_sites, key=lambda s: (len(ic_sets[s]), s)))

growth = intersection_curve(
    train_sites,
    test_sites,
    ic_sets,
    ic_frequencies,
    baseline_sets,
    baseline_frequencies,
    order_policy=ASCENDING_IC_SIZE_TRAIN_ORDER,
)
points = growth["points"]
x = [point["corpus_size"] for point in points]

fig, axis = plt.subplots(figsize=(3.35, 1.8))
series = (
    ("ic_dynamic", "Weighted IC", "#0072B2", "-"),
    ("ic_static", "IC static", "#0072B2", "--"),
    ("baseline_dynamic", "Weighted Baseline", "#D55E00", "-"),
    ("baseline_static", "Baseline static", "#D55E00", "--"),
)
for key, label, color, linestyle in series:
    axis.plot(
        x,
        [100.0 * point[key] for point in points],
        label=label,
        color=color,
        linestyle=linestyle,
        linewidth=1.45,
    )

axis.set_xlim(1, len(train_sites))
axis.set_ylim(-2, 102)
axis.set_xlabel("tp6-Train workloads in corpus")
axis.set_ylabel("Intersection with tp6-Test")
axis.xaxis.set_major_locator(MultipleLocator(4))
axis.xaxis.set_minor_locator(MultipleLocator(1))
axis.set_yticks(range(0, 101, 20))
axis.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
axis.grid(axis="y", color="#d8d8d8", linewidth=0.55)
axis.grid(False, axis="x")
axis.legend(
    loc="lower center",
    bbox_to_anchor=(0.5, 1.01),
    ncol=2,
    frameon=False,
    fontsize=6.5,
    columnspacing=1.2,
    handlelength=2.6,
)
for spine in ("top", "right"):
    axis.spines[spine].set_visible(False)

fig.subplots_adjust(left=0.16, right=0.985, bottom=0.21, top=0.79)
output = Path(sys.argv[1]) / "corpus-growth.pdf"
fig.savefig(output, dpi=300)
with output.with_suffix(".json").open("w") as fh:
    json.dump(growth, fh, indent=2)
    fh.write("\n")
