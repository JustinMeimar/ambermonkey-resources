"""Shared extraction helpers for the JetStream startup fossil."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))


from figure_data import Metric


def child(metric: Metric, key: str) -> Metric:
    if metric.children is None or key not in metric.children:
        raise ValueError(f"missing metric path component {key!r}")
    return metric.children[key]


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
            raise ValueError(f"{run_name}.{'.'.join(path)} is not scalar")
        values.append(metric.scalar.mean)
    return values
