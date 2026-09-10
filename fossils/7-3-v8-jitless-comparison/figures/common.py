"""Shared helpers for the V8 --jitless comparison figure and table.

The Speedometer 3 data comes from this fossil's own records (via the analysis
pipeline / load_stdin). The JetStream 3 SpiderMonkey data is pooled from the
sibling ``7-2-ambermonkey-perf-jetstream`` fossil. JetStream 3 V8 numbers are
maintained in v8_jitless_perf.json.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from pathlib import Path

import matplotlib as mpl
from fossil_figures import FigureData, Metric

FOSSIL_DIR = Path(__file__).resolve().parents[1]
V8_JSON = FOSSIL_DIR / "v8_jitless_perf.json"
JS3_SIBLING = FOSSIL_DIR.parent / "7-2-ambermonkey-perf-jetstream" / "records"
ORACLE_SIBLING = FOSSIL_DIR.parent / "5-6-oracle-corpus" / "records"
SP3_SIBLING = FOSSIL_DIR.parent / "7-2-ambermonkey-perf-s3" / "records"
OCTANE_SIBLING = FOSSIL_DIR.parent / "7-2-ambermonkey-perf-octane" / "records"
OCTANE_SCORE_RE = re.compile(r"^Score \(version \d+\): ([0-9]+(?:\.[0-9]+)?)\s*$")


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


def validate_records(
    data: FigureData, required: tuple[str, ...], family: str
) -> None:
    missing = [v for v in required if v not in data.columns]
    if missing:
        raise ValueError(
            f"missing {family} variants {missing!r}; found "
            f"{sorted(data.column_names)}"
        )
    commits = set()
    for variant in required:
        column = data.columns[variant]
        run_scores(column)
        commits.add(tag_at(column, "meta", "commit"))
    if len(commits) != 1 or "" in commits:
        message = f"{family} records do not share one valid source commit: {commits}"
        if os.environ.get("FOSSIL_FORCE") == "1":
            print(f"warning: {message} (FOSSIL_FORCE=1)", file=sys.stderr)
        else:
            raise ValueError(message)


def load_oracle_speedometer(
    sibling_records: Path = ORACLE_SIBLING,
) -> dict[str, list[float]]:
    """Return the newest commit-matched Speedometer oracle/default samples."""
    from benchmarks import speedometer3

    variants = ("speedometer3-default", "speedometer3-aot-only")
    by_commit: dict[str, dict[str, tuple[str, list[float]]]] = {}

    for entry in sorted(sibling_records.iterdir()):
        manifest_path = entry / "manifest.json"
        results_path = entry / "results.json"
        if not manifest_path.exists() or not results_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        variant = manifest.get("variant")
        commit = (manifest.get("git") or {}).get("commit")
        if variant not in variants or not commit:
            continue

        results = json.loads(results_path.read_text())
        scores = [
            speedometer3.parse_observation(observation, "oracle-speedometer")[
                "score"
            ]
            for observation in results.get("observations", [])
        ]
        if scores:
            by_commit.setdefault(commit, {})[variant] = (entry.name, scores)

    complete = [
        (max(record[variant][0] for variant in variants), record)
        for record in by_commit.values()
        if all(variant in record for variant in variants)
    ]
    if not complete:
        raise ValueError("no commit-matched Speedometer oracle/default records")

    _, newest = max(complete, key=lambda item: item[0])
    return {variant: newest[variant][1] for variant in variants}


def load_sm_speedometer(
    sibling_records: Path = SP3_SIBLING,
) -> dict[str, list[float]]:
    """Return the newest commit-matched SpiderMonkey Speedometer ladder."""
    from benchmarks import speedometer3

    variants = ("aot-corpus-ic", "aot-corpus", "default-no-ion", "default")
    by_commit: dict[str, dict[str, tuple[str, list[float]]]] = {}

    for entry in sorted(sibling_records.iterdir()):
        manifest_path = entry / "manifest.json"
        results_path = entry / "results.json"
        if not manifest_path.exists() or not results_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        variant = manifest.get("variant")
        commit = (manifest.get("git") or {}).get("commit")
        if variant not in variants or not commit:
            continue

        results = json.loads(results_path.read_text())
        scores = [
            speedometer3.parse_observation(observation, "reclamation-speedometer")[
                "score"
            ]
            for observation in results.get("observations", [])
        ]
        if scores:
            by_commit.setdefault(commit, {})[variant] = (entry.name, scores)

    complete = [
        (max(record[variant][0] for variant in variants), record)
        for record in by_commit.values()
        if all(variant in record for variant in variants)
    ]
    if not complete:
        raise ValueError("no commit-matched SpiderMonkey Speedometer ladder records")

    _, newest = max(complete, key=lambda item: item[0])
    return {variant: newest[variant][1] for variant in variants}


def load_sm_octane(
    sibling_records: Path = OCTANE_SIBLING,
) -> dict[str, list[float]]:
    """Return the newest commit-matched SpiderMonkey Octane ladder."""
    variants = ("aot-corpus-ic", "aot-corpus", "default-no-ion", "default")
    by_commit: dict[str, dict[str, tuple[str, list[float]]]] = {}

    for entry in sorted(sibling_records.iterdir()):
        manifest_path = entry / "manifest.json"
        results_path = entry / "results.json"
        if not manifest_path.exists() or not results_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        variant = manifest.get("variant")
        commit = (manifest.get("git") or {}).get("commit")
        if variant not in variants or not commit:
            continue

        results = json.loads(results_path.read_text())
        scores = []
        for observation in results.get("observations", []):
            lines = []
            for key in ("stdout", "stderr"):
                stream = observation.get(key) or []
                lines.extend(stream if isinstance(stream, list) else stream.splitlines())
            matches = [OCTANE_SCORE_RE.match(line) for line in lines]
            scores.extend(float(match.group(1)) for match in matches if match)
        if scores:
            by_commit.setdefault(commit, {})[variant] = (entry.name, scores)

    complete = [
        (max(record[variant][0] for variant in variants), record)
        for record in by_commit.values()
        if all(variant in record for variant in variants)
    ]
    if not complete:
        raise ValueError("no commit-matched SpiderMonkey Octane ladder records")

    _, newest = max(complete, key=lambda item: item[0])
    return {variant: newest[variant][1] for variant in variants}


def load_v8() -> dict:
    """Return the full V8 reference JSON, keyed by workload."""
    if not V8_JSON.exists():
        raise FileNotFoundError(f"missing V8 reference data: {V8_JSON}")
    return json.loads(V8_JSON.read_text())


def v8_columns(v8: dict, workload: str) -> dict:
    workloads = v8.get("workloads") or {}
    if workload not in workloads:
        raise KeyError(
            f"v8_jitless_perf.json has no workload {workload!r}; "
            f"available: {sorted(workloads)}"
        )
    return workloads[workload]["columns"]


def load_sm_jetstream(sibling_records: Path = JS3_SIBLING) -> dict:
    """Latest JS3 SM per-variant sample list, from the sibling fossil records.

    Returns {variant: [score, ...]} with one score per browser iteration.
    Falls back to the ``sm_placeholder`` block in v8_jitless_perf.json when
    the sibling fossil hasn't been buried yet, so a draft figure still
    renders. Real records always win over the placeholder.
    """
    out: dict[str, list[float]] = {}
    if sibling_records.exists():
        latest_per_variant: dict[str, Path] = {}
        for entry in sorted(sibling_records.iterdir()):
            parts = entry.name.split("_")
            if len(parts) < 5:
                continue
            variant = "_".join(parts[3:-1])
            latest_per_variant[variant] = entry
        for variant, run_dir in latest_per_variant.items():
            results = run_dir / "results.json"
            if not results.exists():
                continue
            try:
                record = json.loads(results.read_text())
            except json.JSONDecodeError:
                continue
            scores: list[float] = []
            for obs in record.get("observations", []):
                stdout = obs.get("stdout")
                if isinstance(stdout, list):
                    stdout = "\n".join(stdout)
                if not stdout:
                    continue
                try:
                    payload = json.loads(stdout.strip())
                except json.JSONDecodeError:
                    continue
                score = payload.get("score")
                if isinstance(score, (int, float)) and score > 0:
                    scores.append(float(score))
            if scores:
                out[variant] = scores
    if out:
        return out
    # Draft-only fallback: synthesise a single-sample list per variant from
    # the sm_placeholder block. Remove the block once the sibling fossil is
    # buried and this branch stops firing.
    try:
        v8 = load_v8()
    except FileNotFoundError:
        return {}
    placeholder = (v8.get("sm_placeholder") or {}).get("jetstream3") or {}
    for variant, entry in placeholder.items():
        score = entry.get("score")
        if isinstance(score, (int, float)) and score > 0:
            out[variant] = [float(score)]
    return out


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
        fig.savefig(path.with_suffix(".pdf"))
        fig.savefig(path.with_suffix(".png"), dpi=300)
