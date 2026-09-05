#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit the end-to-end Baseline JIT vs AmberMonkey oracle table.

Only two variants participate: `default-no-ion` (regular Baseline JIT with
Ion off) and `aot-corpus` (AmberMonkey oracle).  The table gives per-variant
score summary and the AmberMonkey/Baseline speedup, plus a small headline
scalar block the paper's constants layer can look up by field.
"""

import json
import os
import statistics
import sys
from pathlib import Path

import numpy as np
from fossil_figures import FigureData, Metric, load_stdin, write_typst_table

PROJECT_DIR = Path(
    os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3])
)
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402


BASELINE = "default-no-ion"
CANDIDATE = "aot-corpus"
VARIANT_ORDER = (BASELINE, CANDIDATE)


def child(metric: Metric, key: str) -> Metric:
    if metric.children is None or key not in metric.children:
        raise ValueError(f"missing metric path component {key!r}")
    return metric.children[key]


def run_scores(column: Metric) -> list[float]:
    runs = child(column, "runs")
    if not runs.children:
        raise ValueError("analysis contains no browser runs")
    out = []
    for name in sorted(runs.children):
        score = child(runs.children[name], "score")
        if score.scalar is None:
            raise ValueError(f"run metric {name}.score is not scalar")
        out.append(score.scalar.mean)
    return out


def check_commits(data: FigureData, variants) -> None:
    commits = set()
    for variant in variants:
        commit = child(child(data.columns[variant], "meta"), "commit").tag
        if commit:
            commits.add(commit)
    if len(commits) > 1:
        message = f"records span multiple source commits: {commits}"
        if os.environ.get("FOSSIL_FORCE") == "1":
            print(f"warning: {message} (FOSSIL_FORCE=1)", file=sys.stderr)
        else:
            raise ValueError(message)


def main():
    data = load_stdin()
    present = [v for v in VARIANT_ORDER if v in data.columns]
    if not present:
        raise SystemExit(
            f"perf_table: none of {list(VARIANT_ORDER)!r} present in analysis "
            f"(found {sorted(data.column_names)})"
        )
    check_commits(data, present)

    scores = {v: run_scores(data.columns[v]) for v in present}
    means = {v: statistics.fmean(scores[v]) for v in present}
    stdevs = {
        v: statistics.stdev(scores[v]) if len(scores[v]) > 1 else 0.0
        for v in present
    }
    ns = {v: len(scores[v]) for v in present}

    baseline_mean = means.get(BASELINE)
    candidate_mean = means.get(CANDIDATE)
    ratio = (
        candidate_mean / baseline_mean
        if baseline_mean and candidate_mean is not None
        else None
    )

    columns = [
        {"key": "variant",       "label": "Variant",             "align": "left",  "format": "str"},
        {"key": "runs",          "label": "Runs",                "align": "right", "format": "int"},
        {"key": "score",         "label": "Score",               "align": "right", "format": "float"},
        {"key": "score_stdev",   "label": "Stdev",               "align": "right", "format": "float"},
        {"key": "ratio_over_baseline", "label": "vs Baseline JIT", "align": "right", "format": "float"},
    ]
    rows = []
    for v in present:
        row_ratio = (
            round(means[v] / baseline_mean, 4)
            if baseline_mean
            else 0.0
        )
        rows.append([
            v,
            ns[v],
            round(means[v], 3),
            round(stdevs[v], 3),
            row_ratio,
        ])

    out_path = Path(sys.argv[1])
    write_typst_table(out_path, columns=columns, rows=rows)

    # Layer headline scalars atop the table so constants.typ can json-field
    # them.  Score is higher-is-better on Speedometer, so a ratio > 1.0 means
    # AmberMonkey is *faster* than the runtime Baseline JIT and a ratio < 1.0
    # is a slowdown.
    payload = json.loads(out_path.read_text())
    payload["source_fossil"] = os.environ.get("FOSSIL_NAME", "7-4-indirection-e2e-s3")
    payload["workload"] = "speedometer3"
    payload["baseline_variant"] = BASELINE
    payload["candidate_variant"] = CANDIDATE
    payload["variants_present"] = present
    if baseline_mean is not None:
        payload["baseline_score_mean"] = baseline_mean
        payload["baseline_score_stdev"] = stdevs[BASELINE]
    if candidate_mean is not None:
        payload["candidate_score_mean"] = candidate_mean
        payload["candidate_score_stdev"] = stdevs[CANDIDATE]
    if ratio is not None:
        payload["am_over_baseline_ratio"] = ratio
        payload["am_over_baseline_slowdown"] = 1.0 - ratio
        if ns[BASELINE] >= 2 and ns[CANDIDATE] >= 2:
            _, lower_error, upper_error = bootstrap_ratio_ci(
                scores[CANDIDATE],
                scores[BASELINE],
                np.random.default_rng(0),
            )
            ratio_low = ratio - lower_error
            ratio_high = ratio + upper_error
            payload["am_over_baseline_ratio_ci95_low"] = ratio_low
            payload["am_over_baseline_ratio_ci95_high"] = ratio_high
            payload["am_over_baseline_slowdown_ci95_low"] = 1.0 - ratio_high
            payload["am_over_baseline_slowdown_ci95_high"] = 1.0 - ratio_low
    payload["runs_per_variant"] = min(ns.values())
    page_cycles = child(child(data.columns[present[0]], "meta"), "page_cycles").scalar
    if page_cycles is not None:
        payload["page_cycles_per_run"] = int(page_cycles.mean)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
