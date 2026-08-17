#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table A — Speedometer 3 memory aggregate at Peak, plus Final for context."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_ORDER = ("default", "default-no-ion", "aot", "aot-corpus")
CHECKPOINTS = ("Peak", "Final")
BASELINE = "default"


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
    data = load_stdin()
    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("aggregate_table: no known variants")

    columns = [
        {"key": "config",                 "label": "config",                 "align": "left",  "format": "str"},
        {"key": "checkpoint",             "label": "checkpoint",             "align": "left",  "format": "str"},
        {"key": "n_procs",                "label": "content procs",          "align": "right", "format": "int"},
        {"key": "anon_exec_pss_mb",       "label": "anon-exec PSS (MB)",     "align": "right", "format": "float"},
        {"key": "libxul_exec_pss_mb",     "label": ".text.aot PSS (MB)",     "align": "right", "format": "float"},
        {"key": "libxul_exec_rss_mb",     "label": ".text.aot RSS (MB)",     "align": "right", "format": "float"},
        {"key": "engine_pss_mb",          "label": "engine PSS total (MB)",  "align": "right", "format": "float"},
        {"key": "per_proc_engine_pss_mb", "label": "engine PSS / proc (MB)", "align": "right", "format": "float"},
        {"key": "reduction_vs_stock",     "label": "engine-PSS Δ vs stock",  "align": "right", "format": "percent"},
    ]

    # Cache per-checkpoint stock reference
    stock_ref = {}
    if BASELINE in variants:
        col = data.columns[BASELINE]
        cps = (col.children or {}).get("checkpoints")
        cp_map = cps.children if (cps and cps.children) else {}
        for cp_name, cp in cp_map.items():
            v = scalar(cp, "engine_pss_mb")
            if v is not None:
                stock_ref[cp_name] = v

    rows = []
    for v in variants:
        col = data.columns[v]
        cps = (col.children or {}).get("checkpoints")
        cp_map = cps.children if (cps and cps.children) else {}
        for cp_name in CHECKPOINTS:
            cp = cp_map.get(cp_name)
            if cp is None:
                continue
            n_procs = scalar(cp, "n_content_procs") or 0
            anon_pss = scalar(cp, "totals", "anon_exec", "pss_mb") or 0
            lx_pss = scalar(cp, "totals", "libxul_exec", "pss_mb") or 0
            lx_rss = scalar(cp, "totals", "libxul_exec", "rss_mb") or 0
            engine_pss = scalar(cp, "engine_pss_mb") or (anon_pss + lx_pss)
            per_proc = scalar(cp, "per_proc_engine_pss_mb") or (engine_pss / n_procs if n_procs else 0)
            ref = stock_ref.get(cp_name)
            reduction = (1.0 - engine_pss / ref) if (ref and v != BASELINE) else 0.0
            rows.append([
                v, cp_name, int(n_procs),
                round(anon_pss, 3),
                round(lx_pss, 3),
                round(lx_rss, 3),
                round(engine_pss, 3),
                round(per_proc, 4),
                round(reduction, 4),
            ])

    write_typst_table(Path(sys.argv[1]), columns=columns, rows=rows)


if __name__ == "__main__":
    main()
