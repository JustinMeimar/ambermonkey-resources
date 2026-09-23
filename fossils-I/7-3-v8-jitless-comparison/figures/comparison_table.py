#!/usr/bin/env python3
"""Emit a V8-vs-SpiderMonkey headroom table for Speedometer 3 and JetStream 3."""

import json
import os
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    load_sm_jetstream,
    load_v8,
    run_scores,
    summarize,
    summarize_column,
    validate_records,
    v8_columns,
)


SM_DEFAULT = "default"
SM_INTERP = "interp-only"
SM_AM = "aot-corpus"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"


def make_row(workload, engine, config, mean, stdev, ratio):
    return [
        workload,
        engine,
        config,
        round(mean, 3),
        round(stdev, 3),
        round(ratio, 4) if ratio else 0.0,
    ]


def sm_summary(scores_by_variant):
    """Return {variant: (mean, stdev, n)} across SM variants."""
    return {v: summarize(scores_by_variant.get(v, []), 0.0) for v in (SM_INTERP, SM_AM, SM_DEFAULT)}


def workload_rows(workload, sm_scores, v8_cols):
    sm = sm_summary(sm_scores)
    sm_default = sm[SM_DEFAULT][0]
    v8 = {
        slug: summarize_column(v8_cols[slug])
        for slug in (V8_DEFAULT, V8_JITLESS)
    }
    v8_default = v8[V8_DEFAULT][0]

    def ratio(mean, denom):
        return mean / denom if denom else 0.0

    rows = [
        make_row(workload, "V8", "default",          *v8[V8_DEFAULT][:2], 1.0 if v8_default else 0.0),
        make_row(workload, "V8", "jitless",          *v8[V8_JITLESS][:2], ratio(v8[V8_JITLESS][0], v8_default)),
        make_row(workload, "SpiderMonkey", "default",         *sm[SM_DEFAULT][:2], 1.0 if sm_default else 0.0),
        make_row(workload, "SpiderMonkey", "interpreter-only", *sm[SM_INTERP][:2], ratio(sm[SM_INTERP][0], sm_default)),
        make_row(workload, "SpiderMonkey", "AmberMonkey",     *sm[SM_AM][:2],     ratio(sm[SM_AM][0], sm_default)),
    ]
    return rows


def main():
    data = load_stdin()
    required = (SM_INTERP, SM_AM, SM_DEFAULT, V8_DEFAULT, V8_JITLESS)
    validate_records(data, required, "comparison")
    v8 = load_v8()

    sp3_sm_scores = {v: run_scores(data.columns[v]) for v in (SM_INTERP, SM_AM, SM_DEFAULT)}
    sp3_v8_cols = {
        variant: {"samples": run_scores(data.columns[variant])}
        for variant in (V8_DEFAULT, V8_JITLESS)
    }

    js3_sm_scores = load_sm_jetstream()
    js3_v8_cols = v8_columns(v8, "jetstream3")

    columns = [
        {"key": "workload",            "label": "Workload",            "align": "left",  "format": "str"},
        {"key": "engine",              "label": "Engine",              "align": "left",  "format": "str"},
        {"key": "configuration",       "label": "Configuration",       "align": "left",  "format": "str"},
        {"key": "score",               "label": "Score",               "align": "right", "format": "float"},
        {"key": "score_stdev",         "label": "Score stdev",         "align": "right", "format": "float"},
        {"key": "fraction_of_default", "label": "Fraction of default", "align": "right", "format": "percent"},
    ]

    rows = workload_rows("Speedometer 3", sp3_sm_scores, sp3_v8_cols) \
         + workload_rows("JetStream 3", js3_sm_scores, js3_v8_cols)

    out_path = Path(sys.argv[1])
    write_typst_table(out_path, columns=columns, rows=rows)

    payload = json.loads(out_path.read_text())
    payload["workloads"] = ["speedometer3", "jetstream3"]
    payload["sp3_sm_runs_per_variant"] = min(len(sp3_sm_scores[v]) for v in sp3_sm_scores)
    payload["js3_sm_runs_per_variant"] = (
        min(len(js3_sm_scores[v]) for v in (SM_INTERP, SM_AM, SM_DEFAULT))
        if all(js3_sm_scores.get(v) for v in (SM_INTERP, SM_AM, SM_DEFAULT))
        else 0
    )
    payload["v8_source"] = {
        "speedometer3": "fossil records",
        "jetstream3": "manual: v8_jitless_perf.json",
    }

    # Headline scalars — SP3 stays back-compatible with the prior single-workload
    # keys, JS3 additions get a js3_ prefix so downstream consumers stay explicit.
    sp3_sm = sm_summary(sp3_sm_scores)
    sp3_v8 = {slug: summarize_column(sp3_v8_cols[slug]) for slug in (V8_DEFAULT, V8_JITLESS)}
    if sp3_v8[V8_DEFAULT][0]:
        payload["v8_jitless_over_default"] = sp3_v8[V8_JITLESS][0] / sp3_v8[V8_DEFAULT][0]
    if sp3_sm[SM_DEFAULT][0]:
        payload["ambermonkey_over_default"] = sp3_sm[SM_AM][0] / sp3_sm[SM_DEFAULT][0]
        payload["interp_only_over_default"] = sp3_sm[SM_INTERP][0] / sp3_sm[SM_DEFAULT][0]

    js3_sm = sm_summary(js3_sm_scores)
    js3_v8 = {slug: summarize_column(js3_v8_cols[slug]) for slug in (V8_DEFAULT, V8_JITLESS)}
    if js3_v8[V8_DEFAULT][0]:
        payload["js3_v8_jitless_over_default"] = js3_v8[V8_JITLESS][0] / js3_v8[V8_DEFAULT][0]
    if js3_sm[SM_DEFAULT][0]:
        payload["js3_ambermonkey_over_default"] = js3_sm[SM_AM][0] / js3_sm[SM_DEFAULT][0]
        payload["js3_interp_only_over_default"] = js3_sm[SM_INTERP][0] / js3_sm[SM_DEFAULT][0]

    payload["source_fossil"] = os.environ["FOSSIL_NAME"]
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
