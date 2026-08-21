#!/usr/bin/env python3
"""8x8 Baseline function static-intersection matrix for the paper."""

import json
import sys

from pairwise import (
    load_counters,
    matrix,
    render_matrix_table,
    static_intersection,
)


def main():
    _ic_sets, _ic_freqs, bl_sets, _bl_freqs = load_counters()
    bl_static = matrix(static_intersection, bl_sets, bl_sets)
    payload = render_matrix_table(bl_static, row_label="Workload")
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
