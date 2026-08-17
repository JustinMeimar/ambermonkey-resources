#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Grouped bars: engine PSS across AWSY tp6 checkpoints, per configuration.

X-axis: AWSY marker lifecycle. One bar per configuration at each marker.
Label above each non-baseline bar shows the percent reduction vs stock.
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    AMBER_BLUE,
    AMBER_PURPLE,
    AMBER_RED,
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    save_at_declared_size,
)


MARKERS = ("TabsOpen", "TabsOpenSettled", "TabsOpenForceGC", "TabsClosedForceGC")
MARKER_LABELS = {
    "TabsOpen":          "Open",
    "TabsOpenSettled":   "Settled",
    "TabsOpenForceGC":   "Open+GC",
    "TabsClosedForceGC": "Closed+GC",
}

# Config family — one entry per JIT configuration. The workload-intensity
# suffix (-warm, -quick) is stripped before lookup so the same figure works
# for any AWSY variant family fed in via --last N.
CONFIG_ORDER = ("stock", "stock-baseline", "aot", "aot-only")
CONFIG_LABELS = {
    "stock":          "stock",
    "stock-baseline": "stock (no Ion)",
    "aot":            "aot",
    "aot-only":       "aot-only",
}
CONFIG_COLORS = {
    "stock":          AMBER_BLUE,
    "stock-baseline": "#6BAED6",
    "aot":            AMBER_PURPLE,
    "aot-only":       AMBER_RED,
}
BASELINE = "stock"
GROUP_WIDTH = 0.82

WORKLOAD_SUFFIXES = ("-quick",)


def base_config(variant):
    """Return the JIT-config family for a variant, stripping a workload
    suffix if present. 'awsy-tp6-aot-only-quick' -> 'aot-only'."""
    name = variant
    for suf in WORKLOAD_SUFFIXES:
        if name.endswith(suf):
            name = name[: -len(suf)]
            break
    if name.startswith("awsy-tp6-"):
        name = name[len("awsy-tp6-"):]
    return name


def scalar(metric, *path):
    m = metric
    for k in path:
        if m.children is None or k not in m.children:
            return None
        m = m.children[k]
    if m.scalar is None:
        return None
    return m.scalar.mean


def main():
    apply_amber_style("single")
    data = load_stdin()

    # Map every incoming variant column to its family (stripping -warm/-quick).
    # If several variants of the same family appear (e.g. mixed workload
    # intensities), the last one wins with a warning; callers should use
    # --last N against a single family.
    family_variant = {}
    for col_name in data.columns:
        fam = base_config(col_name)
        if fam not in CONFIG_ORDER:
            continue
        if fam in family_variant and family_variant[fam] != col_name:
            sys.stderr.write(
                f"marker_bars: warning: multiple variants for family "
                f"{fam!r}: {family_variant[fam]!r} and {col_name!r}; "
                f"keeping the latter\n"
            )
        family_variant[fam] = col_name

    configs = [c for c in CONFIG_ORDER if c in family_variant]
    if not configs:
        raise SystemExit("marker_bars: no known variants in analysis output")

    # cells[config][marker] = engine_pss_mb (may be missing).
    cells = {c: {} for c in configs}
    for c in configs:
        col = data.columns[family_variant[c]]
        if col.children is None or "checkpoints" not in col.children:
            continue
        cps = col.children["checkpoints"].children or {}
        for m in MARKERS:
            if m not in cps:
                continue
            v = scalar(cps[m], "engine_pss_mb")
            if v is not None:
                cells[c][m] = v

    n_configs = len(configs)
    bar_width = GROUP_WIDTH / n_configs
    x = np.arange(len(MARKERS))

    fig, ax = plt.subplots(figsize=figure_size("single", 2.5))

    highest = 0.0
    for i, cfg in enumerate(configs):
        offset = (i - (n_configs - 1) / 2) * bar_width
        xs, means, deltas = [], [], []
        for j, mk in enumerate(MARKERS):
            v = cells[cfg].get(mk)
            if v is None:
                continue
            xs.append(x[j] + offset)
            means.append(v)
            highest = max(highest, v)
            stock_v = cells.get(BASELINE, {}).get(mk)
            if cfg != BASELINE and stock_v and stock_v > 0:
                deltas.append(f"{(v / stock_v - 1.0) * 100:+.0f}%")
            else:
                deltas.append("")

        bars = ax.bar(
            xs,
            means,
            bar_width * 0.92,
            label=CONFIG_LABELS[cfg],
            color=CONFIG_COLORS[cfg],
            edgecolor="white",
            linewidth=0.35,
            zorder=3,
        )
        if cfg != BASELINE:
            ax.bar_label(
                bars,
                labels=deltas,
                padding=2,
                rotation=90,
                fontsize=FONT_SIZES["annotation"],
            )

    ax.set_xticks(x)
    ax.set_xticklabels([MARKER_LABELS[m] for m in MARKERS])
    ax.set_ylabel("engine PSS (MB, Σ content procs)")
    ax.set_ylim(0, highest * 1.28 if highest else 1)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", zorder=0)
    ax.tick_params(axis="x", length=0, pad=3)
    ax.margins(x=0.02)

    if n_configs > 1:
        ax.legend(
            frameon=False,
            loc="upper right",
            borderaxespad=0.4,
            handlelength=1.2,
            labelspacing=0.25,
            ncol=min(n_configs, 2),
        )

    fig.subplots_adjust(left=0.17, right=0.995, top=0.96, bottom=0.14)
    save_at_declared_size(fig, sys.argv[1])


if __name__ == "__main__":
    main()
