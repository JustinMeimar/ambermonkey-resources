#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit a Speedometer 3 V8-vs-SpiderMonkey table (paper-shaped JSON)."""

import json
import os
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_v8, run_scores, summarize, validate_sm


SM_DEFAULT = "default"
SM_INTERP = "interp-only"
SM_AM = "aot-corpus"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"


def make_row(engine, config, mean, stdev, ratio):
    return [engine, config, round(mean, 3), round(stdev, 3), round(ratio, 4)]


def main():
    data = load_stdin()
    validate_sm(data, (SM_INTERP, SM_AM, SM_DEFAULT))
    v8 = load_v8()

    sm_scores = {v: run_scores(data.columns[v]) for v in (SM_INTERP, SM_AM, SM_DEFAULT)}
    sm_summary = {v: summarize(sm_scores[v], 0.0) for v in sm_scores}
    sm_default = sm_summary[SM_DEFAULT][0]

    v8_summary = {
        slug: summarize(
            v8["columns"][slug].get("samples", []),
            v8["columns"][slug].get("score", 0.0),
        )
        for slug in (V8_DEFAULT, V8_JITLESS)
    }
    v8_default = v8_summary[V8_DEFAULT][0]

    columns = [
        {"key": "engine",              "label": "Engine",              "align": "left",  "format": "str"},
        {"key": "configuration",       "label": "Configuration",       "align": "left",  "format": "str"},
        {"key": "score",               "label": "Score",               "align": "right", "format": "float"},
        {"key": "score_stdev",         "label": "Score stdev",         "align": "right", "format": "float"},
        {"key": "fraction_of_default", "label": "Fraction of default", "align": "right", "format": "percent"},
    ]

    rows = [
        make_row("V8", "default", *v8_summary[V8_DEFAULT][:2], 1.0),
        make_row(
            "V8", "jitless", *v8_summary[V8_JITLESS][:2],
            v8_summary[V8_JITLESS][0] / v8_default if v8_default else 0.0,
        ),
        make_row("SpiderMonkey", "default", *sm_summary[SM_DEFAULT][:2], 1.0),
        make_row(
            "SpiderMonkey", "interpreter-only", *sm_summary[SM_INTERP][:2],
            sm_summary[SM_INTERP][0] / sm_default if sm_default else 0.0,
        ),
        make_row(
            "SpiderMonkey", "AmberMonkey", *sm_summary[SM_AM][:2],
            sm_summary[SM_AM][0] / sm_default if sm_default else 0.0,
        ),
    ]

    out_path = Path(sys.argv[1])
    write_typst_table(out_path, columns=columns, rows=rows)

    payload = json.loads(out_path.read_text())
    payload["workload"] = "speedometer3"
    payload["sm_runs_per_variant"] = min(len(sm_scores[v]) for v in sm_scores)
    payload["v8_source"] = "manual: v8_jitless_sp3_perf.json"
    if v8_default:
        payload["v8_jitless_over_default"] = v8_summary[V8_JITLESS][0] / v8_default
    if sm_default:
        payload["ambermonkey_over_default"] = sm_summary[SM_AM][0] / sm_default
        payload["interp_only_over_default"] = sm_summary[SM_INTERP][0] / sm_default
    payload["source_fossil"] = os.environ.get("FOSSIL_NAME", "7-3-v8-jitless-comparison")
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
