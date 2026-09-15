#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table A — headline aggregate: engine PSS/USS across configs at TabsOpenForceGC."""

import json
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_ORDER = ("awsy-tp6-stock", "awsy-tp6-stock-baseline",
                 "awsy-tp6-aot", "awsy-tp6-aot-only",
                 "awsy-tp6-stock-quick", "awsy-tp6-stock-baseline-quick",
                 "awsy-tp6-aot-quick", "awsy-tp6-aot-only-quick")
ANCHOR = "TabsOpenForceGC"
FALLBACK = "TabsOpenSettled"


def family_baseline(variant):
    """Reduction column compares each variant to its family's plain 'stock'
    (default JIT). Family is determined by the workload-intensity suffix:
    -quick (--entities 4) or default. Mixing families in one table is fine;
    each row uses its own reference."""
    if variant.endswith("-quick"):
        return "awsy-tp6-stock-quick"
    return "awsy-tp6-stock"


def scalar(metric, *path):
    m = metric
    for k in path:
        if m.children is None or k not in m.children:
            return None
        m = m.children[k]
    if m.scalar is None:
        return None
    return m.scalar.mean


def anchor_of(col):
    """Return the checkpoint metric present under this variant."""
    if col.children is None or "checkpoints" not in col.children:
        return None, None
    cps = col.children["checkpoints"].children or {}
    for name in (ANCHOR, FALLBACK):
        if name in cps:
            return name, cps[name]
    return None, None


def main():
    data = load_stdin()
    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("aggregate_table: no known variants")

    rows_data = []
    family_stock_pss = {}
    for v in variants:
        col = data.columns[v]
        name, cp = anchor_of(col)
        if cp is None:
            continue
        n_procs = scalar(cp, "n_content_procs") or 0
        anon_pss = scalar(cp, "totals", "anon_exec", "pss_mb") or 0
        anon_uss = scalar(cp, "totals", "anon_exec", "uss_mb") or 0
        lx_pss = scalar(cp, "totals", "libxul_exec", "pss_mb") or 0
        lx_rss = scalar(cp, "totals", "libxul_exec", "rss_mb") or 0
        engine_pss = scalar(cp, "engine_pss_mb") or (anon_pss + lx_pss)
        per_proc_pss = scalar(cp, "per_proc_engine_pss_mb") or (engine_pss / n_procs if n_procs else 0)
        # Cache the plain-stock engine PSS for each workload family so the
        # reduction column below can look it up without depending on iteration
        # order. Do not let 'stock-baseline*' overwrite plain stock.
        if v == family_baseline(v):
            family_stock_pss[v] = engine_pss
        rows_data.append({
            "config": v, "checkpoint": name,
            "n_procs": int(n_procs),
            "anon_exec_pss_mb": round(anon_pss, 3),
            "anon_exec_uss_mb": round(anon_uss, 3),
            "libxul_exec_pss_mb": round(lx_pss, 3),
            "libxul_exec_rss_mb": round(lx_rss, 3),
            "engine_pss_mb": round(engine_pss, 3),
            "per_proc_engine_pss_mb": round(per_proc_pss, 4),
        })

    columns = [
        {"key": "config",                 "label": "config",                 "align": "left",  "format": "str"},
        {"key": "checkpoint",             "label": "checkpoint",             "align": "left",  "format": "str"},
        {"key": "n_procs",                "label": "content procs",          "align": "right", "format": "int"},
        {"key": "anon_exec_pss_mb",       "label": "anon-exec PSS (MB)",     "align": "right", "format": "float"},
        {"key": "anon_exec_uss_mb",       "label": "anon-exec USS (MB)",     "align": "right", "format": "float"},
        {"key": "libxul_exec_pss_mb",     "label": ".text.aot PSS (MB)",     "align": "right", "format": "float"},
        {"key": "libxul_exec_rss_mb",     "label": ".text.aot RSS (MB)",     "align": "right", "format": "float"},
        {"key": "engine_pss_mb",          "label": "engine PSS total (MB)",  "align": "right", "format": "float"},
        {"key": "per_proc_engine_pss_mb", "label": "engine PSS / proc (MB)", "align": "right", "format": "float"},
        {"key": "reduction_vs_stock",     "label": "engine-PSS Δ vs stock",  "align": "right", "format": "percent"},
    ]

    rows = []
    for r in rows_data:
        baseline_name = family_baseline(r["config"])
        baseline_pss = family_stock_pss.get(baseline_name)
        is_baseline = r["config"] == baseline_name
        if baseline_pss and baseline_pss > 0 and not is_baseline:
            reduction = 1.0 - r["engine_pss_mb"] / baseline_pss
        else:
            reduction = 0.0
        rows.append([
            r["config"], r["checkpoint"], r["n_procs"],
            r["anon_exec_pss_mb"], r["anon_exec_uss_mb"],
            r["libxul_exec_pss_mb"], r["libxul_exec_rss_mb"],
            r["engine_pss_mb"], r["per_proc_engine_pss_mb"],
            round(reduction, 4),
        ])

    out = Path(sys.argv[1])
    write_typst_table(out, columns=columns, rows=rows)


if __name__ == "__main__":
    main()
