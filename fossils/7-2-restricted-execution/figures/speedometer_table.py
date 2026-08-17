#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit the Speedometer 3.1 tier-ladder table."""

import json
import os
import statistics
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import child, run_values, validate_data


BASELINE = "interp-only"
DEFAULT = "default"
VARIANT_ORDER = ("interp-only", "aot-corpus", "default-no-ion", "default")


def main():
    data = load_stdin()
    validate_data(data, baseline=BASELINE)

    variants = [v for v in VARIANT_ORDER if v in data.columns]
    if not variants:
        raise SystemExit("speedometer_table: no known variants in analysis output")

    scores = {v: run_values(data.columns[v], "score") for v in variants}
    means = {v: statistics.fmean(scores[v]) for v in variants}
    stdevs = {
        v: statistics.stdev(scores[v]) if len(scores[v]) > 1 else 0.0
        for v in variants
    }

    base_score = means[BASELINE]
    default_score = means[DEFAULT] if DEFAULT in means else means[variants[-1]]

    columns = [
        {"key": "variant",           "label": "Variant",        "align": "left",  "format": "str"},
        {"key": "score",             "label": "Score",          "align": "right", "format": "float"},
        {"key": "score_stdev",       "label": "Score stdev",    "align": "right", "format": "float"},
        {"key": "ratio_over_interp", "label": "vs interp-only", "align": "right", "format": "float"},
        {"key": "ratio_over_default","label": "vs default",     "align": "right", "format": "float"},
    ]

    rows = [
        [
            v,
            round(means[v], 3),
            round(stdevs[v], 3),
            round(means[v] / base_score, 4),
            round(means[v] / default_score, 4),
        ]
        for v in variants
    ]

    aot = means.get("aot-corpus")
    interp = means.get(BASELINE)
    default = means.get(DEFAULT)
    runs_per_variant = min(len(scores[v]) for v in variants)
    page_cycles = int(
        child(data.columns[variants[0]], "meta").children["page_cycles"].scalar.mean
    )

    out_path = Path(sys.argv[1])
    write_typst_table(out_path, columns=columns, rows=rows)

    # Layer headline scalars atop the table so constants.typ can json-field them.
    payload = json.loads(out_path.read_text())
    if aot is not None and interp is not None:
        payload["aot_over_interp_ratio"] = aot / interp
        payload["aot_over_interp_speedup"] = aot / interp - 1.0
    if aot is not None and default is not None:
        payload["aot_over_default_ratio"] = aot / default
    payload["source_fossil"] = os.environ.get("FOSSIL_NAME", "7-3-ambermonkey-perf")
    payload["workload"] = "speedometer3"
    payload["runs_per_variant"] = runs_per_variant
    payload["page_cycles_per_run"] = page_cycles
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
