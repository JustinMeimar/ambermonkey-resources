#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Table B — verbose per-bucket census at TabsOpenForceGC."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_ORDER = ("awsy-tp6-stock", "awsy-tp6-stock-baseline",
                 "awsy-tp6-aot", "awsy-tp6-aot-only",
                 "awsy-tp6-stock-quick", "awsy-tp6-stock-baseline-quick",
                 "awsy-tp6-aot-quick", "awsy-tp6-aot-only-quick")
BUCKETS = ("libxul_exec", "libxul_rodata", "libxul_rw",
           "anon_exec", "anon_rw", "other_file", "other_anon")
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


def anchor_of(col):
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
        raise SystemExit("bucket_table: no known variants")

    columns = [
        {"key": "config",           "label": "config",                 "align": "left",  "format": "str"},
        {"key": "bucket",           "label": "bucket",                 "align": "left",  "format": "str"},
        {"key": "pss_mb",           "label": "PSS (MB)",               "align": "right", "format": "float"},
        {"key": "uss_mb",           "label": "USS (MB)",               "align": "right", "format": "float"},
        {"key": "rss_mb",           "label": "RSS (MB, Σ procs)",      "align": "right", "format": "float"},
        {"key": "shared_clean_mb",  "label": "shared clean (MB)",      "align": "right", "format": "float"},
        {"key": "private_dirty_mb", "label": "private dirty (MB)",     "align": "right", "format": "float"},
        {"key": "vma_count",        "label": "VMAs (Σ)",               "align": "right", "format": "int"},
    ]

    rows = []
    for v in variants:
        _, cp = anchor_of(data.columns[v])
        if cp is None:
            continue
        for b in BUCKETS:
            rows.append([
                v, b,
                round(scalar(cp, "totals", b, "pss_mb") or 0, 3),
                round(scalar(cp, "totals", b, "uss_mb") or 0, 3),
                round(scalar(cp, "totals", b, "rss_mb") or 0, 3),
                round(scalar(cp, "totals", b, "shared_clean_mb") or 0, 3),
                round(scalar(cp, "totals", b, "private_dirty_mb") or 0, 3),
                int(scalar(cp, "totals", b, "vma_count") or 0),
            ])

    write_typst_table(Path(sys.argv[1]), columns=columns, rows=rows)


if __name__ == "__main__":
    main()
