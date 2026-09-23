#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table D — engine PSS over the AWSY marker lifecycle."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_ORDER = ("awsy-tp6-stock", "awsy-tp6-stock-baseline",
                 "awsy-tp6-aot", "awsy-tp6-aot-only",
                 "awsy-tp6-stock-quick", "awsy-tp6-stock-baseline-quick",
                 "awsy-tp6-aot-quick", "awsy-tp6-aot-only-quick")
MARKER_ORDER = ("TabsOpen", "TabsOpenSettled", "TabsOpenForceGC", "TabsClosedForceGC")


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
        raise SystemExit("marker_progression_table: no known variants")

    columns = [
        {"key": "config",             "label": "config",           "align": "left",  "format": "str"},
        {"key": "marker",             "label": "marker",           "align": "left",  "format": "str"},
        {"key": "n_procs",            "label": "content procs",    "align": "right", "format": "int"},
        {"key": "engine_pss_mb",      "label": "engine PSS (MB)",  "align": "right", "format": "float"},
        {"key": "anon_exec_pss_mb",   "label": "anon-exec PSS",    "align": "right", "format": "float"},
        {"key": "libxul_exec_pss_mb", "label": ".text.aot PSS",    "align": "right", "format": "float"},
    ]

    rows = []
    for v in variants:
        col = data.columns[v]
        if col.children is None or "checkpoints" not in col.children:
            continue
        cps = col.children["checkpoints"].children or {}
        for m in MARKER_ORDER:
            if m not in cps:
                continue
            cp = cps[m]
            rows.append([
                v, m,
                int(scalar(cp, "n_content_procs") or 0),
                round(scalar(cp, "engine_pss_mb") or 0, 3),
                round(scalar(cp, "totals", "anon_exec", "pss_mb") or 0, 3),
                round(scalar(cp, "totals", "libxul_exec", "pss_mb") or 0, 3),
            ])

    write_typst_table(Path(sys.argv[1]), columns=columns, rows=rows)


if __name__ == "__main__":
    main()
