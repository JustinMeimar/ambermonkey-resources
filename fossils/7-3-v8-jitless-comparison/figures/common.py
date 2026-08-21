"""Shared helpers for the V8 --jitless comparison figure and table."""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

import matplotlib as mpl
from fossil_figures import FigureData, Metric


FOSSIL_DIR = Path(__file__).resolve().parents[1]
V8_JSON = FOSSIL_DIR / "v8_jitless_sp3_perf.json"


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


def run_scores(column: Metric) -> list[float]:
    runs = child(column, "runs")
    if not runs.children:
        raise ValueError("analysis contains no browser runs")
    out = []
    for run_name in sorted(runs.children):
        score = child(runs.children[run_name], "score")
        if score.scalar is None:
            raise ValueError(f"run metric {run_name}.score is not scalar")
        out.append(score.scalar.mean)
    return out


def validate_sm(data: FigureData, required: tuple[str, ...]) -> None:
    missing = [v for v in required if v not in data.columns]
    if missing:
        raise ValueError(
            f"missing SpiderMonkey variants {missing!r}; found "
            f"{sorted(data.column_names)}"
        )
    commits = set()
    for variant in required:
        column = data.columns[variant]
        run_scores(column)
        commits.add(tag_at(column, "meta", "commit"))
    if len(commits) != 1 or "" in commits:
        message = f"SpiderMonkey records do not share one valid source commit: {commits}"
        if os.environ.get("FOSSIL_FORCE") == "1":
            print(f"warning: {message} (FOSSIL_FORCE=1)", file=sys.stderr)
        else:
            raise ValueError(message)


def load_v8() -> dict:
    """Return {slug: {"samples": [...], "score": float, "note": str}} plus meta."""
    if not V8_JSON.exists():
        raise FileNotFoundError(f"missing V8 reference data: {V8_JSON}")
    return json.loads(V8_JSON.read_text())


def summarize(
    samples: list[float],
    fallback_score: float,
    fallback_stdev: float = 0.0,
    fallback_n: int = 0,
) -> tuple[float, float, int]:
    """Return (mean, stdev, n). Uses fallback fields when samples is empty."""
    if samples:
        mean = statistics.fmean(samples)
        stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
        return mean, stdev, len(samples)
    return float(fallback_score), float(fallback_stdev), int(fallback_n)


def summarize_column(column: dict) -> tuple[float, float, int]:
    """Summarize a v8 column dict, threading its stdev/iterations fallbacks."""
    return summarize(
        column.get("samples", []),
        column.get("score", 0.0),
        column.get("stdev", 0.0),
        column.get("iterations", 0),
    )


def save_png_and_pdf(fig, output_path: str) -> None:
    path = Path(output_path)
    with mpl.rc_context({"savefig.bbox": None}):
        fig.savefig(path)
        fig.savefig(path.with_suffix(".pdf"))
