#!/usr/bin/env python3
"""NxN Baseline function dynamic-intersection matrix for the paper.

Rows are the source workload supplying identities; columns are the
evaluated workload contributing per-body entry counts.
"""

import json
import sys
from pathlib import Path

from pairwise import (
    dynamic_intersection,
    load_counters,
    matrix,
    render_matrix_table,
)


def main():
    sites, _ic_sets, _ic_freqs, bl_sets, bl_freqs = load_counters()
    bl_dynamic = matrix(dynamic_intersection, bl_sets, bl_freqs, sites)
    payload = render_matrix_table(bl_dynamic, sites, row_label="Source")
    if len(sys.argv) > 1:
        with open((Path(sys.argv[1]) / "baseline-dynamic.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
