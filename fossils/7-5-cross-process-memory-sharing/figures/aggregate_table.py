#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table A — Speedometer 3 memory aggregate at Peak.

Reports the metrics that support the sharing-validation claim: .text.aot
RSS/PSS ratio (how well the image shares across content procs), per-proc
engine PSS (per-content-process footprint), and the anon-exec segment
(private JIT memory that the AOT-only variant eliminates). We do not
report a reduction-vs-stock column: the aot-only variant runs a different
tier profile than stock, so a direct % delta would conflate the AOT image
with tier restriction. Final checkpoint is omitted from the paper table
because process-teardown ordering makes it too noisy to interpret."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


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
    data = load_stdin()
    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("aggregate_table: no known variants")

    columns = [
        {"key": "config",                 "label": "config",                 "align": "left",  "format": "str"},
        {"key": "n_procs",                "label": "content procs",          "align": "right", "format": "int"},
        {"key": "libxul_exec_rss_mb",     "label": ".text.aot RSS (MB)",     "align": "right", "format": "float"},
        {"key": "libxul_exec_pss_mb",     "label": ".text.aot PSS (MB)",     "align": "right", "format": "float"},
        {"key": "sharing_ratio",          "label": "RSS/PSS (sharing)",      "align": "right", "format": "float"},
        {"key": "anon_exec_pss_mb",       "label": "anon-exec PSS (MB)",     "align": "right", "format": "float"},
        {"key": "per_proc_engine_pss_mb", "label": "engine PSS / proc (MB)", "align": "right", "format": "float"},
    ]

    rows = []
    for v in variants:
        col = data.columns[v]
        cps = (col.children or {}).get("checkpoints")
        cp_map = cps.children if (cps and cps.children) else {}
        cp = cp_map.get(CHECKPOINT)
        if cp is None:
            continue
        n_procs = scalar(cp, "n_content_procs") or 0
        anon_pss = scalar(cp, "totals", "anon_exec", "pss_mb") or 0
        lx_pss = scalar(cp, "totals", "libxul_exec", "pss_mb") or 0
        lx_rss = scalar(cp, "totals", "libxul_exec", "rss_mb") or 0
        engine_pss = scalar(cp, "engine_pss_mb") or (anon_pss + lx_pss)
        per_proc = scalar(cp, "per_proc_engine_pss_mb") or (engine_pss / n_procs if n_procs else 0)
        sharing = (lx_rss / lx_pss) if lx_pss > 0 else 0.0
        rows.append([
            v, int(n_procs),
            round(lx_rss, 2),
            round(lx_pss, 2),
            round(sharing, 2),
            round(anon_pss, 2),
            round(per_proc, 2),
        ])

    write_typst_table(Path(sys.argv[1]), columns=columns, rows=rows)


if __name__ == "__main__":
    main()
