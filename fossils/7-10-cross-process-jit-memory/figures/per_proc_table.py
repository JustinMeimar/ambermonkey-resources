#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table C — per-content-process validation. One row per (variant, pid) at
TabsOpenForceGC (from run_01, since PID sets differ across iterations).

Sanity target: anon-exec RSS == PSS == USS (Linux invariant); libxul .text
RSS >> PSS (shared file-backed).
"""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_ORDER = ("awsy-tp6-stock", "awsy-tp6-stock-baseline",
                 "awsy-tp6-aot", "awsy-tp6-aot-only",
                 "awsy-tp6-stock-quick", "awsy-tp6-stock-baseline-quick",
                 "awsy-tp6-aot-quick", "awsy-tp6-aot-only-quick")
ANCHOR = "TabsOpenForceGC"
FALLBACK = "TabsOpenSettled"


def scalar(metric, *path):
    m = metric
    for k in path:
        if m.children is None or k not in m.children:
            return None
        m = m.children[k]
    if m.scalar is None:
        return None
    return m.scalar.mean


def first_run(col):
    """Return the metric for the first (lowest-numbered) run under `runs`."""
    if col.children is None or "runs" not in col.children:
        return None
    runs = col.children["runs"].children or {}
    if not runs:
        return None
    return runs[sorted(runs)[0]]


def anchor_from_run(run_metric):
    if run_metric.children is None or "checkpoints" not in run_metric.children:
        return None
    cps = run_metric.children["checkpoints"].children or {}
    for name in (ANCHOR, FALLBACK):
        if name in cps:
            return cps[name]
    return None


def main():
    data = load_stdin()
    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("per_proc_table: no known variants")

    columns = [
        {"key": "config",             "label": "config",           "align": "left",  "format": "str"},
        {"key": "pid",                "label": "pid",              "align": "right", "format": "int"},
        {"key": "anon_exec_rss_mb",   "label": "anon-exec RSS",    "align": "right", "format": "float"},
        {"key": "anon_exec_pss_mb",   "label": "anon-exec PSS",    "align": "right", "format": "float"},
        {"key": "anon_exec_uss_mb",   "label": "anon-exec USS",    "align": "right", "format": "float"},
        {"key": "libxul_exec_rss_mb", "label": ".text.aot RSS",    "align": "right", "format": "float"},
        {"key": "libxul_exec_pss_mb", "label": ".text.aot PSS",    "align": "right", "format": "float"},
        {"key": "libxul_exec_uss_mb", "label": ".text.aot USS",    "align": "right", "format": "float"},
    ]

    rows = []
    for v in variants:
        run = first_run(data.columns[v])
        if run is None:
            continue
        cp = anchor_from_run(run)
        if cp is None or cp.children is None or "per_proc" not in cp.children:
            continue
        per_proc = cp.children["per_proc"].children or {}
        pid_rows = []
        for key, proc in per_proc.items():
            pid = int(scalar(proc, "pid") or 0)
            pid_rows.append([
                v, pid,
                round(scalar(proc, "anon_exec_rss_mb") or 0, 3),
                round(scalar(proc, "anon_exec_pss_mb") or 0, 3),
                round(scalar(proc, "anon_exec_uss_mb") or 0, 3),
                round(scalar(proc, "libxul_exec_rss_mb") or 0, 3),
                round(scalar(proc, "libxul_exec_pss_mb") or 0, 3),
                round(scalar(proc, "libxul_exec_uss_mb") or 0, 3),
            ])
        pid_rows.sort(key=lambda r: -r[2])  # descending anon-exec RSS
        rows.extend(pid_rows)

    write_typst_table(Path(sys.argv[1]), columns=columns, rows=rows)


if __name__ == "__main__":
    main()
