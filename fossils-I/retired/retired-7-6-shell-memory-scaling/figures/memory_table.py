#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit a per-worker memory table (scaling-jit or scaling-rss, selected by FOSSIL_TABLE_NAME)."""

import os
import re
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


VARIANT_RE = re.compile(r"^n(\d+)-(stock-base|stock-full|aot-restricted|aot-full)$")

KINDS = ("stock-base", "stock-full", "aot-restricted", "aot-full")


def scalar(metric, key):
    return metric.children[key].scalar.mean


def slope(pairs):
    """Ordinary least-squares slope of y vs x."""
    n = len(pairs)
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def reduction(base, aot):
    return 1.0 - aot / base if base > 0 else 0.0


def build_rows(by_n, metric_key):
    Ns = sorted(n for n, v in by_n.items() if all(k in v for k in KINDS))
    if not Ns:
        raise SystemExit(f"memory_table: no complete four-way rows for {metric_key}")

    rows = []
    for n in Ns:
        stock_base = by_n[n]["stock-base"][metric_key]
        stock_full = by_n[n]["stock-full"][metric_key]
        aot_rest   = by_n[n]["aot-restricted"][metric_key]
        aot_full   = by_n[n]["aot-full"][metric_key]
        rows.append([
            str(n),
            stock_base,
            aot_rest,
            reduction(stock_base, aot_rest),
            stock_full,
            aot_full,
            reduction(stock_full, aot_full),
        ])

    Ns_fit = [n for n in Ns if n > 1]
    if len(Ns_fit) >= 2:
        def col_slope(kind):
            return slope([(n, by_n[n][kind][metric_key]) for n in Ns_fit])
        s_base = col_slope("stock-base")
        s_full = col_slope("stock-full")
        s_rest = col_slope("aot-restricted")
        s_afull = col_slope("aot-full")
        rows.append([
            "slope-mb-per-N",
            s_base, s_rest, reduction(s_base, s_rest),
            s_full, s_afull, reduction(s_full, s_afull),
        ])
    return rows


TABLE_TO_METRIC = {
    "scaling-jit": "anon",
    "scaling-rss": "rss",
}


def main():
    data = load_stdin()

    by_n = {}
    for variant, metric in data.columns.items():
        match = VARIANT_RE.match(variant)
        if not match:
            continue
        n = int(match.group(1))
        kind = match.group(2)
        by_n.setdefault(n, {})[kind] = {
            "anon": scalar(metric, "peak_anon_exec_mb"),
            "rss":  scalar(metric, "peak_rss_mb"),
        }

    columns = [
        {"key": "workers",              "label": "N",                     "align": "right", "format": "str"},
        {"key": "stock_base_mb",        "label": "stock --no-ion",        "align": "right", "format": "float"},
        {"key": "aot_restricted_mb",    "label": "aot --aot-only",        "align": "right", "format": "float"},
        {"key": "restricted_reduction", "label": "restricted Δ",          "align": "right", "format": "percent"},
        {"key": "stock_full_mb",        "label": "stock default",         "align": "right", "format": "float"},
        {"key": "aot_full_mb",          "label": "aot",                   "align": "right", "format": "float"},
        {"key": "full_reduction",       "label": "full-tier Δ",           "align": "right", "format": "percent"},
    ]

    table_name = os.environ.get("FOSSIL_TABLE_NAME", "scaling-jit")
    metric_key = TABLE_TO_METRIC.get(table_name)
    if metric_key is None:
        raise SystemExit(
            f"memory_table: unknown FOSSIL_TABLE_NAME {table_name!r}; "
            f"expected one of {sorted(TABLE_TO_METRIC)}"
        )

    if metric_key == "rss":
        columns = [dict(c) for c in columns]
        for c in columns[1:]:
            if c["key"].endswith("_mb"):
                c["label"] = c["label"] + " (RSS)"

    write_typst_table(
        Path(sys.argv[1]),
        columns=columns,
        rows=build_rows(by_n, metric_key),
    )


if __name__ == "__main__":
    main()
