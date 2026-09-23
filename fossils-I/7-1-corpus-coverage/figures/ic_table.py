#!/usr/bin/env python3
"""IC-stub coverage table."""

from _common import emit_aggregate

ROWS = [
    ("#ICs",                 "utilization.ic_stubs.total",    "count"),
    ("Corpus utilization",   "utilization.ic_stubs.pct",      "percent"),
    ("Compilation requests", "requests.ic_stubs.total",       "count"),
    ("AOT request coverage", "requests.ic_stubs.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_aggregate("ic_table", ROWS)
