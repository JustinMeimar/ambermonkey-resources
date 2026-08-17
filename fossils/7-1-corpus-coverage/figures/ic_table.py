#!/usr/bin/env python3
"""IC-stub coverage table."""

from _common import emit_aggregate

ROWS = [
    ("Corpus size",    "utilization.ic_stubs.total",    "count"),
    ("Attached",       "utilization.ic_stubs.used",     "count"),
    ("Utilization",    "utilization.ic_stubs.pct",      "percent"),
    ("Total attaches", "requests.ic_stubs.total",       "count"),
    ("AOT hit rate",   "requests.ic_stubs.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_aggregate("ic_table", ROWS)
