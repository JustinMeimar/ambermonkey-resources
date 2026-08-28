#!/usr/bin/env python3
"""Summarise 3-3 inter-workload records into a paper-consumable JSON."""

import json
import statistics
import sys

from pairwise import (
    dynamic_intersection,
    load_counters,
    matrix,
    static_intersection,
)


def off_diagonal(m, n):
    return [m[i][j] for i in range(n) for j in range(n) if i != j]


def stats(values):
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "median": statistics.median(values),
        "mean": statistics.mean(values),
        "q1": q1,
        "q3": q3,
        "min": min(values),
        "max": max(values),
    }


def main():
    sites, ic_sets, ic_freqs, bl_sets, bl_freqs = load_counters()
    n = len(sites)

    # Both matrices are directional (|A ∩ B| / |B|-shaped), so both
    # sample the full n*(n-1) off-diagonal.
    bl_static  = off_diagonal(matrix(static_intersection, bl_sets, bl_sets, sites), n)
    ic_static  = off_diagonal(matrix(static_intersection, ic_sets, ic_sets, sites), n)
    bl_dynamic = off_diagonal(matrix(dynamic_intersection, bl_sets,  bl_freqs, sites), n)
    ic_dynamic = off_diagonal(matrix(dynamic_intersection, ic_sets,  ic_freqs, sites), n)

    output = {
        "sites": list(sites),
        "site_count": n,
        "static_pair_count": len(ic_static),
        "off_diagonal_count": len(ic_dynamic),
        "ic": {
            "static":  stats(ic_static),
            "dynamic": stats(ic_dynamic),
        },
        "baseline": {
            "static":  stats(bl_static),
            "dynamic": stats(bl_dynamic),
        },
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
