#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Compressed horizontal per-microbench cycles: Baseline JIT vs AmberMonkey.

Renders only the five targeted micro-benchmarks (the three IC controls are
dropped) as grouped horizontal bars, one group per bench.  Style follows the
V8 --jitless comparison: single-column, minimal chrome, value annotations at
each bar tip.

Reads observations from the paper-cohort.json records directly (bypassing
the standard analyze pipeline, which refuses on any empty-stdout observation
in the wider records set).  Mirrors the collection logic in
scripts/emit_cycles_table.py.
"""

import json
import os
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

FOSSIL_DIR = Path(__file__).resolve().parents[1]
RECORDS_DIR = FOSSIL_DIR / "records"
COHORT_PATH = FOSSIL_DIR / "paper-cohort.json"

BUILDS = ("default", "opt", "no-opt")
PLOT_BUILDS = ("default", "opt")
BENCHES = ("interrupt-check", "stack-check", "prebarrier", "vm-call", "abi-call")
LABELS = {
    "interrupt-check": "Interrupt",
    "stack-check": "Stack",
    "prebarrier": "Pre-barrier",
    "vm-call": "VM call",
    "abi-call": "ABI call",
}
ITER_COUNTS = {
    "interrupt-check": 10_000_000_000,
    "stack-check":     500_000_000,
    "prebarrier":      500_000_000,
    "vm-call":         20_000_000,
    "abi-call":        100_000_000,
}
REQUIRED_EVENTS = ("cycles:u", "instructions:u", "ref-cycles:u")
MIN_RUNNING = 99.5

CONFIG_FOR_BUILD = {"default": "default-no-ion", "opt": "aot-corpus"}
LEGEND_LABELS = {"default": "Baseline JIT", "opt": "AmberMonkey"}
CONFIGS = load_configurations()
COLORS = {build: CONFIGS[slug]["color"] for build, slug in CONFIG_FOR_BUILD.items()}
GROUP_HEIGHT = 0.72
FILL_ALPHA = 0.55


def split_variant(variant):
    for build in sorted(BUILDS, key=len, reverse=True):
        suffix = "-" + build
        if variant.endswith(suffix):
            return variant[: -len(suffix)], build
    return None, None


def parse_perf_ndjson(text):
    events = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = obj.get("event")
        val = obj.get("counter-value")
        if event is None or val is None:
            continue
        try:
            value = float(val)
        except (TypeError, ValueError):
            return None
        try:
            pcnt = float(obj.get("pcnt-running", 0.0))
        except (TypeError, ValueError):
            pcnt = 0.0
        events[event] = {"value": value, "pcnt": pcnt}
    return events


def obs_stdout(obs):
    s = obs.get("stdout", "")
    if isinstance(s, list):
        s = "\n".join(s)
    return s if isinstance(s, str) else ""


def cycles_per_iter(obs, iter_count):
    events = parse_perf_ndjson(obs_stdout(obs))
    if events is None:
        return None
    for req in REQUIRED_EVENTS:
        if req not in events or events[req]["pcnt"] < MIN_RUNNING:
            return None
    return events["cycles:u"]["value"] / iter_count


def collect_cohort():
    cohort = json.loads(COHORT_PATH.read_text())
    cells = {}
    for variant, dirname in cohort.items():
        bench, build = split_variant(variant)
        if bench is None or bench not in BENCHES or build not in PLOT_BUILDS:
            continue
        results = json.loads((RECORDS_DIR / dirname / "results.json").read_text())
        samples = []
        for obs in results.get("observations", []):
            if int(obs.get("exit_code", 1)) != 0:
                continue
            cpi = cycles_per_iter(obs, ITER_COUNTS[bench])
            if cpi is not None:
                samples.append(cpi)
        if not samples:
            continue
        mean = statistics.fmean(samples)
        stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
        cells.setdefault(bench, {})[build] = (mean, stdev)
    return cells


apply_amber_style("single")
cells = collect_cohort()
if not cells:
    raise SystemExit("cycles_hbars: no matching microbench data in paper cohort")

benches = [b for b in BENCHES if b in cells]
n_benches = len(benches)
n_builds = len(PLOT_BUILDS)
bar_height = GROUP_HEIGHT / n_builds

# Top-to-bottom in listed order.
y_group = np.arange(n_benches)[::-1]

fig, ax = plt.subplots(figsize=figure_size("single", 1.75))

highest = 0.0
for i, build in enumerate(PLOT_BUILDS):
    # Baseline JIT sits above AmberMonkey within each pair.
    offset = ((n_builds - 1) / 2 - i) * bar_height
    ys, means, stddevs = [], [], []
    for j, bench in enumerate(benches):
        value = cells[bench].get(build)
        if value is None:
            continue
        ys.append(y_group[j] + offset)
        means.append(value[0])
        stddevs.append(value[1])
        highest = max(highest, value[0] + value[1])

    face = to_rgba(COLORS[build], FILL_ALPHA)
    ax.barh(
        ys,
        means,
        height=bar_height * 0.92,
        xerr=stddevs,
        label=LEGEND_LABELS[build],
        color=face,
        edgecolor=COLORS[build],
        linewidth=0.7,
        error_kw={"elinewidth": 0.7, "capthick": 0.7, "capsize": 1.6, "ecolor": "#333"},
        zorder=3,
    )
    for yi, mean, err in zip(ys, means, stddevs):
        ax.text(
            mean + err + highest * 0.008,
            yi,
            f"{mean:.0f}",
            ha="left",
            va="center",
            fontsize=FONT_SIZES["annotation"],
        )

ax.set_yticks(y_group)
ax.set_yticklabels([LABELS.get(b, b) for b in benches])
ax.set_xlabel("User cycles / iteration")
ax.set_xlim(0, highest * 1.14 if highest else 1)
ax.set_ylim(-0.55, n_benches - 0.45)
ax.grid(axis="x", visible=True, linestyle=":", color="#BBBBBB", linewidth=0.6, zorder=0)
ax.grid(axis="y", visible=False)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0, pad=3)

ax.legend(
    frameon=False,
    loc="lower right",
    bbox_to_anchor=(1.0, 1.005),
    ncol=n_builds,
    handlelength=1.2,
    handletextpad=0.4,
    columnspacing=1.2,
    borderaxespad=0,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.20, right=0.985, top=0.86, bottom=0.20)
fig.savefig(Path(sys.argv[1]).with_suffix(".pdf"))
fig.savefig(Path(sys.argv[1]).with_suffix(".png"), dpi=300)
