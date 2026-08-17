#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Stacked composition bars: engine PSS per variant at the Peak checkpoint,
split into anon-exec (private, hatched) and libxul-exec (shared, solid).
Right axis: libxul RSS/PSS sharing ratio as circle markers.

Story: this is a sharing-validation figure, not a memory-reduction figure.
The `.text.aot` segment (solid) stays near-fully-shared across content procs
(RSS/PSS approaches n_procs); the anon-exec segment (hatched) is per-proc
private JIT memory that only exists when the runtime is emitting Baseline/IC
code. aot-corpus is the only variant that eliminates that private segment,
but because it also forbids fallback compilation it does not have a
tier-profile-matched comparison group — the figure therefore reports raw
segment sizes rather than a reduction percentage."""

import os
import statistics
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_variant_colors,
    save_at_declared_size,
)


VARIANT_ORDER = ("default", "default-no-ion", "aot", "aot-corpus")
DISPLAY_NAMES = {
    "default":        "default",
    "default-no-ion": "no-Ion",
    "aot":            "aot",
    "aot-corpus":     "aot-only",
}
CHECKPOINT = "Peak"
ANON_HATCH = "////"


def scalar(metric, *path):
    m = metric
    for k in path:
        if m.children is None or k not in m.children:
            return None
        m = m.children[k]
    if m.scalar is None:
        return None
    return m.scalar.mean, m.scalar.stddev


def main():
    apply_amber_style("single")
    data = load_stdin()
    colors = load_variant_colors()

    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("composition_bars: no known variants in analysis output")

    cells = {}
    for v in variants:
        col = data.columns[v]
        cps = (col.children or {}).get("checkpoints")
        cp_map = cps.children if (cps and cps.children) else {}
        cp = cp_map.get(CHECKPOINT)
        if cp is None:
            continue
        anon = scalar(cp, "totals", "anon_exec", "pss_mb")
        lx_pss = scalar(cp, "totals", "libxul_exec", "pss_mb")
        lx_rss = scalar(cp, "totals", "libxul_exec", "rss_mb")
        engine = scalar(cp, "engine_pss_mb")
        n_procs = scalar(cp, "n_content_procs")
        if anon is None or lx_pss is None:
            continue
        anon_m, anon_sd = anon
        lx_pss_m, lx_pss_sd = lx_pss
        lx_rss_m, _ = lx_rss if lx_rss else (0.0, 0.0)
        engine_m = engine[0] if engine else (anon_m + lx_pss_m)
        engine_sd = engine[1] if engine else 0.0
        n_m = n_procs[0] if n_procs else 0
        share_ratio = (lx_rss_m / lx_pss_m) if lx_pss_m > 0 else 0.0
        cells[v] = {
            "anon_mean": anon_m, "anon_sd": anon_sd,
            "libxul_mean": lx_pss_m, "libxul_sd": lx_pss_sd,
            "engine_mean": engine_m, "engine_sd": engine_sd,
            "libxul_rss_mean": lx_rss_m,
            "share_ratio": share_ratio,
            "n_procs": n_m,
        }

    if not cells:
        raise SystemExit(f"composition_bars: no {CHECKPOINT} checkpoint present")

    xs = np.arange(len(variants))
    bar_width = 0.62

    fig, ax = plt.subplots(figsize=figure_size("single", 2.75))
    ax2 = ax.twinx()

    highest = 0.0

    for i, v in enumerate(variants):
        c = cells.get(v)
        if c is None:
            continue
        color = colors[v]
        # libxul (shared) — solid, from 0.
        ax.bar(
            xs[i], c["libxul_mean"], bar_width,
            color=color, edgecolor="white", linewidth=0.4, zorder=3,
        )
        # anon (private) — same color, hatched, stacked on top.
        ax.bar(
            xs[i], c["anon_mean"], bar_width,
            bottom=c["libxul_mean"],
            color=color, edgecolor="white", linewidth=0.4,
            hatch=ANON_HATCH, alpha=0.75, zorder=3,
        )
        # Total-height error bar at the engine PSS top.
        if c["engine_sd"] > 0:
            ax.errorbar(
                xs[i], c["engine_mean"], yerr=c["engine_sd"],
                fmt="none", ecolor="#333", elinewidth=0.7, capsize=2, zorder=4,
            )
        # Raw MB labels on segments so readers can do their own arithmetic
        # without leaning on a reduction% callout. Anon label goes above the
        # bar (or is omitted when the private segment is negligible); libxul
        # label sits inside the shared segment.
        ax.text(
            xs[i], c["libxul_mean"] / 2.0,
            f"{c['libxul_mean']:.0f}",
            ha="center", va="center",
            fontsize=FONT_SIZES["annotation"],
            color="white", zorder=5,
        )
        if c["anon_mean"] >= 3.0:
            ax.text(
                xs[i], c["engine_mean"] + max(c["engine_sd"], 1.2),
                f"+{c['anon_mean']:.0f} anon",
                ha="center", va="bottom",
                fontsize=FONT_SIZES["annotation"],
                color="#333", zorder=5,
            )
        highest = max(highest, c["engine_mean"] + c["engine_sd"])

    # Right axis: sharing ratio (libxul RSS / libxul PSS).
    ratios = [cells[v]["share_ratio"] if v in cells else 0.0 for v in variants]
    ax2.plot(
        xs, ratios,
        linestyle="none", marker="o", markersize=6,
        markerfacecolor="white", markeredgecolor="#222", markeredgewidth=1.1,
        zorder=6,
    )
    for i, r in enumerate(ratios):
        if r > 0:
            ax2.text(
                xs[i] + 0.24, r, f"{r:.1f}×",
                ha="left", va="center",
                fontsize=FONT_SIZES["annotation"], color="#222",
            )

    ax.set_xticks(xs)
    ax.set_xticklabels(
        [DISPLAY_NAMES.get(v, v) for v in variants],
        rotation=0, ha="center",
        fontsize=FONT_SIZES["tick"],
    )
    ax.set_ylabel("engine PSS (MB, Σ content procs)")
    ax.set_ylim(0, highest * 1.22 if highest else 1)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", zorder=0)
    ax.tick_params(axis="x", length=0, pad=3)

    ax2.set_ylabel(".text.aot RSS / PSS (sharing)")
    if ratios:
        rmax = max(ratios)
        ax2.set_ylim(0, rmax * 1.35 if rmax else 1)
    ax2.grid(False)

    # Legend explains the stack semantics (not the variants; those are labelled
    # on the x-axis). One grey key for anon and one for libxul, plus the marker.
    stack_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="#BBBBBB", hatch=ANON_HATCH,
                      edgecolor="white", alpha=0.75, label="anon-exec (private)"),
        plt.Rectangle((0, 0), 1, 1, facecolor="#BBBBBB",
                      edgecolor="white", label=".text.aot (shared libxul-exec)"),
        plt.Line2D([0], [0], marker="o", markersize=6, linestyle="none",
                   markerfacecolor="white", markeredgecolor="#222",
                   markeredgewidth=1.1, label="RSS / PSS"),
    ]
    ax.legend(
        handles=stack_handles,
        frameon=False,
        loc="upper right",
        bbox_to_anchor=(1.0, 1.02),
        borderaxespad=0,
        handlelength=1.4,
        labelspacing=0.25,
        fontsize=FONT_SIZES["legend"],
    )

    fig.subplots_adjust(left=0.14, right=0.86, top=0.94, bottom=0.14)
    save_at_declared_size(fig, sys.argv[1])


if __name__ == "__main__":
    main()
