#!/usr/bin/env python3
"""Summarise 3-3 inter-workload records into a paper-consumable JSON."""

import json
import statistics
import sys

from pairwise import (
    SITES,
    dynamic_intersection,
    load_counters,
    matrix,
    static_intersection,
)


def off_diagonal(m):
    n = len(SITES)
    return [m[i][j] for i in range(n) for j in range(n) if i != j]


def per_target_range(m):
    n = len(SITES)
    ranges = {}
    for j, tgt in enumerate(SITES):
        vals = [m[i][j] for i in range(n) if i != j]
        ranges[tgt] = {"min": min(vals), "max": max(vals)}
    return ranges


def find_argmin_pair(m):
    n = len(SITES)
    best = None
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if best is None or m[i][j] < best[0]:
                best = (m[i][j], SITES[i], SITES[j])
    return {"value": best[0], "corpus": best[1], "target": best[2]}


def main():
    ic_sets, ic_freqs, bl_sets, bl_freqs = load_counters()

    bl_static = matrix(static_intersection, bl_sets, bl_sets)
    ic_static = matrix(static_intersection, ic_sets, ic_sets)
    bl_dynamic = matrix(dynamic_intersection, bl_sets, bl_freqs)
    ic_dynamic = matrix(dynamic_intersection, ic_sets, ic_freqs)

    ic_off = off_diagonal(ic_dynamic)
    ge_thresh = 0.95
    ic_ge = sum(1 for v in ic_off if v >= ge_thresh)

    bl_dyn_off = off_diagonal(bl_dynamic)
    bl_stat_off = off_diagonal(bl_static)

    output = {
        "sites": list(SITES),
        "site_count": len(SITES),
        "off_diagonal_count": len(ic_off),
        "medians": {
            "baseline_jaccard": statistics.median(bl_stat_off),
            "ic_jaccard": statistics.median(off_diagonal(ic_static)),
            "baseline_coverage": statistics.median(bl_dyn_off),
            "ic_coverage": statistics.median(ic_off),
        },
        "baseline_coverage_per_target": per_target_range(bl_dynamic),
        "ic_coverage_per_target": per_target_range(ic_dynamic),
        "ic_coverage_threshold": ge_thresh,
        "ic_coverage_pairs_at_or_above_threshold": ic_ge,
        "ic_coverage_argmin": find_argmin_pair(ic_dynamic),
        "baseline_coverage_max": max(bl_dyn_off),
        "baseline_static_max": max(bl_stat_off),
    }

    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            json.dump(output, fh, indent=2, sort_keys=True)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
