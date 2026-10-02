#!/usr/bin/env python3
"""Speedometer 3 restricted performance as a fraction of engine default."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import os

import numpy as np
from figure_data import parse_data

PROJECT_DIR = Path(__file__).resolve().parents[3]
from figure_style import (  # noqa: E402
    apply_amber_style,
    load_configurations,
)
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402

from common import (  # noqa: E402
    load_oracle_speedometer,
    load_sm_speedometer,
    run_scores,
    save_png_and_pdf,
    validate_records,
)
from reclamation_plot import render_reclamation_bars  # noqa: E402


SM_IC = "aot-corpus-ic"
SM_AM = "aot-corpus"
SM_ORACLE = "aot-oracle"
SM_BASELINE = "default-no-ion"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"
CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")

BAR_LABELS = {
    SM_IC: "AM-IC",
    SM_AM: "AM",
    SM_ORACLE: "AM-Oracle",
    SM_BASELINE: "Baseline JIT",
    V8_JITLESS: "V8 Jitless",
}
BAR_COLORS = {
    SM_IC: CONFIGS[SM_IC]["color"],
    SM_AM: CONFIGS[SM_AM]["color"],
    SM_ORACLE: CONFIGS[SM_ORACLE]["color"],
    SM_BASELINE: CONFIGS[SM_BASELINE]["color"],
    V8_JITLESS: CONFIGS[V8_JITLESS]["color"],
}


def ratio_bar(slug, scores, default_scores, rng):
    if len(scores) >= 2 and len(default_scores) >= 2:
        ratio, lower_error, upper_error = bootstrap_ratio_ci(
            scores, default_scores, rng
        )
    else:
        ratio = np.mean(scores) / np.mean(default_scores)
        lower_error = upper_error = 0.0
    return {
        "slug": slug,
        "ratio": ratio,
        "lower_error": lower_error,
        "upper_error": upper_error,
    }


apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
validate_records(data, (V8_DEFAULT, V8_JITLESS), "V8 comparison")

sm = load_sm_speedometer()
oracle = load_oracle_speedometer()
v8_default = run_scores(data.columns[V8_DEFAULT])
rng = np.random.default_rng(0)

bars = [
    ratio_bar(SM_IC, sm[SM_IC], sm["default"], rng),
    ratio_bar(SM_AM, sm[SM_AM], sm["default"], rng),
    ratio_bar(
        SM_ORACLE,
        oracle["speedometer3-aot-only"],
        oracle["speedometer3-default"],
        rng,
    ),
    ratio_bar(SM_BASELINE, sm[SM_BASELINE], sm["default"], rng),
    ratio_bar(V8_JITLESS, run_scores(data.columns[V8_JITLESS]), v8_default, rng),
]
for bar in bars:
    bar["label"] = BAR_LABELS[bar["slug"]]
    bar["color"] = BAR_COLORS[bar["slug"]]
    bar["hatch"] = "///" if bar["slug"] == SM_BASELINE else ""

render_reclamation_bars(
    bars,
    "Speedometer 3.1 score (% of engine default)",
    save_png_and_pdf,
    sys.argv[1],
)
