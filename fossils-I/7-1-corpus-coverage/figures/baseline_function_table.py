#!/usr/bin/env python3
"""Baseline-function coverage table."""

from _common import emit_aggregate

ROWS = [
    ("#BL Functions",        "utilization.baseline_functions.total",    "count"),
    ("Corpus utilization",   "utilization.baseline_functions.pct",      "percent"),
    ("Compilation requests", "requests.baseline_functions.total",       "count"),
    ("AOT request coverage", "requests.baseline_functions.aot_hit_pct", "percent"),
]

if __name__ == "__main__":
    emit_aggregate("baseline_function_table", ROWS)
