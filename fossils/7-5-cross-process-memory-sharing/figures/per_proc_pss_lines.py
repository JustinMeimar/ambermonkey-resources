#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-content-process engine PSS across configurations, decomposed into
its shared (.text.aot) and private (anon-exec) components.

Single MB axis, three lines. The story reads left-to-right: as the tier
ladder moves from stock JIT emission (Default / Baseline) into AmberMonkey,
the private anon-exec line collapses toward zero while the shared line
stays roughly flat, so total per-proc engine PSS drops.

Complement to composition_bars.py (that figure shows Σ-across-procs on a
dual axis and is useful when the reader cares about aggregate footprint;
this one shows per-proc and is useful when the reader cares about
marginal cost of an additional content process)."""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    AMBER_GREY,
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
    save_at_declared_size,
)


CONFIGS = load_configurations()
VARIANT_ORDER = ("interp-only", "default", "default-no-ion", "aot", "aot-corpus")
CHECKPOINT = "Peak"


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

    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("per_proc_pss_lines: no known variants in analysis output")

    rows = []
    for v in variants:
        col = data.columns[v]
        cps = (col.children or {}).get("checkpoints")
        cp_map = cps.children if (cps and cps.children) else {}
        cp = cp_map.get(CHECKPOINT)
        if cp is None:
            continue
        n_procs = scalar(cp, "n_content_procs") or 0
        if n_procs <= 0:
            continue
        anon = scalar(cp, "totals", "anon_exec", "pss_mb") or 0.0
        lx_pss = scalar(cp, "totals", "libxul_exec", "pss_mb") or 0.0
        engine = scalar(cp, "engine_pss_mb")
        if engine is None:
            engine = anon + lx_pss
        rows.append({
            "slug": v,
            "n_procs": n_procs,
            "shared": lx_pss / n_procs,
            "private": anon / n_procs,
            "total": engine / n_procs,
        })

    if not rows:
        raise SystemExit(f"per_proc_pss_lines: no {CHECKPOINT} checkpoint present")

    xs = np.arange(len(rows))
    shared = [r["shared"] for r in rows]
    private = [r["private"] for r in rows]
    total = [r["total"] for r in rows]

    total_color = "#222222"
    shared_color = "#2166AC"
    private_color = "#B2182B"

    fig, ax = plt.subplots(figsize=figure_size("single", 1.95))

    ax.plot(xs, total, color=total_color, linewidth=1.6, marker="o",
            markersize=4.5, markerfacecolor=total_color, zorder=5,
            label="Total")
    ax.plot(xs, shared, color=shared_color, linewidth=1.2, marker="s",
            markersize=4, markerfacecolor=shared_color, zorder=4,
            label="Shared")
    ax.plot(xs, private, color=private_color, linewidth=1.2, marker="^",
            markersize=4.5, markerfacecolor=private_color, linestyle=(0, (4, 2)),
            zorder=4, label="Private")

    def label(x, y, text, color, dy):
        ax.annotate(text, xy=(x, y),
                    xytext=(0, dy), textcoords="offset points",
                    ha="center", va="bottom" if dy >= 0 else "top",
                    fontsize=FONT_SIZES["annotation"], color=color)

    for i, r in enumerate(rows):
        label(xs[i], r["total"], f"{r['total']:.1f}", total_color, 7)
        # Skip Shared/Private labels that would sit on top of the Total
        # label (interp-only: shared == total; aot-corpus: total ≈ shared).
        if abs(r["shared"] - r["total"]) > 0.4:
            label(xs[i], r["shared"], f"{r['shared']:.1f}", shared_color, -6)
        if r["private"] >= 0.3:
            label(xs[i], r["private"], f"{r['private']:.1f}", private_color, 7)

    ax.set_xticks(xs)
    ax.set_xticklabels(
        [CONFIGS[r["slug"]]["long"] for r in rows],
        rotation=20, ha="right", rotation_mode="anchor",
        fontsize=FONT_SIZES["tick"],
    )
    ax.set_xlabel("")
    ax.set_ylabel("PSS per Process (MB)")
    ax.set_ylim(0, max(total) * 1.15)
    ax.set_xlim(-0.35, len(rows) - 1 + 0.35)
    ax.grid(axis="y", zorder=0, linewidth=0.4, color=AMBER_GREY, alpha=0.4)
    ax.grid(axis="x", visible=False)
    ax.tick_params(axis="x", length=0, pad=3)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=3,
        borderaxespad=0,
        handlelength=2.0,
        columnspacing=1.2,
        fontsize=FONT_SIZES["legend"],
    )

    fig.subplots_adjust(left=0.16, right=0.98, top=0.84, bottom=0.30)
    save_at_declared_size(fig, sys.argv[1])


if __name__ == "__main__":
    main()
