#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Cross-workload concentration summary table for the intra-workload paragraph."""

import statistics
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


def scalar(metric, key):
    return metric.children[key].scalar.mean


def main():
    data = load_stdin()
    sites = sorted(data.columns)
    if not sites:
        raise SystemExit("concentration_summary: no variants in analysis output")

    per_site = []
    for site in sites:
        m = data.columns[site]
        per_site.append((site, scalar(m, "top_10_share"), int(scalar(m, "bodies_90"))))

    shares = [row[1] for row in per_site]
    body_counts = [row[2] for row in per_site]

    reference = data.columns[sites[0]]
    top_fraction = scalar(reference, "top_fraction")
    coverage_fraction = scalar(reference, "coverage_fraction")

    rows = [list(r) for r in per_site]
    rows.append(["median", statistics.median(shares), int(statistics.median(body_counts))])
    rows.append(["min", min(shares), min(body_counts)])
    rows.append(["max", max(shares), max(body_counts)])
    rows.append(["params", top_fraction, int(round(coverage_fraction * 100))])

    write_typst_table(
        Path(sys.argv[1]).with_suffix(".json"),
        columns=[
            {"key": "workload", "label": "Workload", "align": "left", "format": "str"},
            {"key": "top10_share", "label": "Top 10% share", "align": "right", "format": "percent"},
            {"key": "bodies_90", "label": "Bodies to 90%", "align": "right", "format": "int"},
        ],
        rows=rows,
    )


if __name__ == "__main__":
    main()
