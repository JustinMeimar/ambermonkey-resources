#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Grouped bar chart of peak per-process anonymous-executable RSS across the Octane suite."""

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import apply_style, load_stdin


VARIANT_RE = re.compile(r"^(?P<bench>[a-z0-9-]+)-(?P<kind>interp|baseline|stock|aot-only|aot)$")

KINDS = ("baseline", "stock", "aot", "aot-only")
LABELS = {
    "baseline": "baseline (--no-ion)",
    "stock":    "stock (default)",
    "aot":      "aot (--aot)",
    "aot-only": "aot-only (--aot --aot-only)",
}
COLORS = {
    "baseline": "#E8553A",
    "stock":    "#F18F01",
    "aot":      "#44AF69",
    "aot-only": "#2E86AB",
}
GROUP_WIDTH = 0.86


def scalar(metric, key):
    child = metric.children.get(key)
    if child is None:
        return None, None
    return child.scalar.mean, child.scalar.stddev


def collect(data, mb_key):
    by_bench = {}
    for variant, metric in data.columns.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        bench = match.group("bench")
        kind = match.group("kind")
        mean, stddev = scalar(metric, mb_key)
        if mean is None:
            continue
        by_bench.setdefault(bench, {})[kind] = (mean, stddev)
    return {b: cells for b, cells in by_bench.items() if all(k in cells for k in KINDS)}


def render(by_bench, ylabel, title, out_path):
    benches = sorted(by_bench, key=lambda b: by_bench[b]["baseline"][0], reverse=True)
    n = len(benches)
    bar_w = GROUP_WIDTH / len(KINDS)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(9.0, 0.75 * n + 3.0), 4.4))

    for i, kind in enumerate(KINDS):
        offset = (i - (len(KINDS) - 1) / 2) * bar_w
        means = [by_bench[b][kind][0] for b in benches]
        stds  = [by_bench[b][kind][1] for b in benches]
        ax.bar(
            x + offset, means, bar_w, yerr=stds,
            label=LABELS[kind], color=COLORS[kind], edgecolor="none",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(benches, rotation=35, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False, loc="upper right", fontsize=8, ncol=3)
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main():
    apply_style(column="double")
    data = load_stdin()

    out = Path(sys.argv[1])

    render(
        collect(data, "peak_anon_exec_mb"),
        ylabel="peak anon-exec RSS (MB)",
        title="Per-process JIT code footprint across the Octane suite (N=1)",
        out_path=out,
    )
    render(
        collect(data, "peak_anon_mb"),
        ylabel="peak private-anonymous RSS (MB)",
        title="Per-process private anonymous RSS across the Octane suite (N=1)",
        out_path=out.with_name("anon-bars" + out.suffix),
    )


if __name__ == "__main__":
    main()
