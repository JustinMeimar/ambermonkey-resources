"""Shared data extraction, validation, and output helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from fossil_figures import FigureData, Metric


def child(metric: Metric, key: str) -> Metric:
    if metric.children is None or key not in metric.children:
        raise ValueError(f"missing metric path component {key!r}")
    return metric.children[key]


def tag_at(metric: Metric, *path: str) -> str:
    for key in path:
        metric = child(metric, key)
    if metric.tag is None:
        raise ValueError(f"metric {'.'.join(path)!r} is not a tag")
    return metric.tag


def scalar_at(metric: Metric, *path: str) -> float:
    for key in path:
        metric = child(metric, key)
    if metric.scalar is None:
        raise ValueError(f"metric {'.'.join(path)!r} is not scalar")
    return metric.scalar.mean


def run_values(column: Metric, *path: str) -> list[float]:
    runs = child(column, "runs")
    if not runs.children:
        raise ValueError("analysis contains no browser runs")

    values = []
    for run_name in sorted(runs.children):
        metric = runs.children[run_name]
        for key in path:
            metric = child(metric, key)
        if metric.scalar is None:
            raise ValueError(
                f"run metric {run_name}.{'.'.join(path)} is not scalar"
            )
        values.append(metric.scalar.mean)
    return values


def validate_data(data: FigureData, baseline: str = "interp-only") -> None:
    variants = data.column_names
    if baseline not in data.columns:
        raise ValueError(
            f"missing baseline variant {baseline!r}; found {sorted(variants)}"
        )

    commits = set()
    workload_names = None
    for variant in variants:
        column = data.columns[variant]
        run_values(column, "score")

        commits.add(tag_at(column, "meta", "commit"))
        scalar_at(column, "meta", "page_cycles")
        workloads = set(child(column, "workloads_ms").children or {})
        if len(workloads) != 20:
            raise ValueError(
                f"{variant}: expected 20 workload totals, found {len(workloads)}"
            )
        if workload_names is None:
            workload_names = workloads
        elif workloads != workload_names:
            raise ValueError(f"{variant}: workload set differs from other variants")

    if len(commits) != 1 or "" in commits:
        raise ValueError(f"records do not share one valid source commit: {commits}")


def save_png_and_pdf(fig, output_path: str) -> None:
    path = Path(output_path)
    # Fossil's general style uses bbox_inches="tight", which can silently
    # change publication widths. Preserve the declared 3.33/7.0-inch sizes.
    with mpl.rc_context({"savefig.bbox": None}):
        fig.savefig(path)
        fig.savefig(path.with_suffix(".pdf"))
