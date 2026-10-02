#!/usr/bin/env python3
"""Speedometer 3.1 and Octane 2.0 performance retained by JIT configuration."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))
from figure_runtime import use_project_python

use_project_python()


import os

import matplotlib.pyplot as plt
import numpy as np
from figure_data import parse_data

PROJECT_DIR = Path(__file__).resolve().parents[3]
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

from common import (  # noqa: E402
    run_scores,
    save_png_and_pdf,
    validate_records,
)
from reclamation_plot import draw_reclamation_bars  # noqa: E402


SM_AM = "aot-corpus"
SM_ORACLE = "aot-oracle"
SM_BASELINE = "default-no-ion"
SM_DEFAULT = "default"
SP3_AM = "speedometer-am"
SP3_ORACLE = "speedometer-am-oracle"
SP3_BASELINE = "speedometer-baseline"
SP3_DEFAULT = "speedometer-default"
V8_DEFAULT = "speedometer-v8-default"
V8_JITLESS = "speedometer-v8-jitless"
V8_JITLESS_STYLE = "v8-jitless"
OCTANE_AM = "octane-am"
OCTANE_ORACLE = "octane-am-oracle"
OCTANE_BASELINE = "octane-baseline"
OCTANE_DEFAULT = "octane-default"
OCTANE_V8_DEFAULT = "octane-v8-default"
OCTANE_V8_JITLESS = "octane-v8-jitless"

CONFIGS = load_configurations(PROJECT_DIR / "configurations.toml")
LABELS = {
    SM_AM: "AM",
    SM_ORACLE: "AM-Oracle",
    SM_BASELINE: "Baseline JIT",
    V8_JITLESS_STYLE: "V8 Jitless",
}
COLORS = {
    slug: CONFIGS[slug]["color"]
    for slug in (SM_AM, SM_ORACLE, SM_BASELINE, V8_JITLESS_STYLE)
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
        "label": LABELS[slug],
        "color": COLORS[slug],
        "hatch": "///" if slug == SM_BASELINE else "",
    }


def panel_bars(
    am_scores,
    default_scores,
    oracle_scores,
    oracle_default_scores,
    baseline_scores,
    v8_jitless,
    v8_default,
    rng,
):
    return [
        ratio_bar(SM_AM, am_scores, default_scores, rng),
        ratio_bar(SM_ORACLE, oracle_scores, oracle_default_scores, rng),
        ratio_bar(SM_BASELINE, baseline_scores, default_scores, rng),
        ratio_bar(V8_JITLESS_STYLE, v8_jitless, v8_default, rng),
    ]


apply_amber_style("single")
data = parse_data(json.load(sys.stdin))
validate_records(
    data,
    (SP3_AM, SP3_ORACLE, SP3_BASELINE, SP3_DEFAULT),
    "Speedometer SpiderMonkey comparison",
)
validate_records(data, (V8_DEFAULT, V8_JITLESS), "Speedometer V8 comparison")
validate_records(
    data,
    (OCTANE_AM, OCTANE_ORACLE, OCTANE_BASELINE, OCTANE_DEFAULT),
    "Octane SpiderMonkey comparison",
)
validate_records(data, (OCTANE_V8_DEFAULT, OCTANE_V8_JITLESS), "Octane V8 comparison")

rng = np.random.default_rng(0)
speedometer_bars = panel_bars(
    run_scores(data.columns[SP3_AM]),
    run_scores(data.columns[SP3_DEFAULT]),
    run_scores(data.columns[SP3_ORACLE]),
    run_scores(data.columns[SP3_DEFAULT]),
    run_scores(data.columns[SP3_BASELINE]),
    run_scores(data.columns[V8_JITLESS]),
    run_scores(data.columns[V8_DEFAULT]),
    rng,
)
octane_bars = panel_bars(
    run_scores(data.columns[OCTANE_AM]),
    run_scores(data.columns[OCTANE_DEFAULT]),
    run_scores(data.columns[OCTANE_ORACLE]),
    run_scores(data.columns[OCTANE_DEFAULT]),
    run_scores(data.columns[OCTANE_BASELINE]),
    run_scores(data.columns[OCTANE_V8_JITLESS]),
    run_scores(data.columns[OCTANE_V8_DEFAULT]),
    rng,
)

fig, axes = plt.subplots(2, 1, figsize=figure_size("single", 3.15))
speedometer_handles = draw_reclamation_bars(
    axes[0], speedometer_bars, "Score (% of engine default)", legend=False
)
draw_reclamation_bars(
    axes[1], octane_bars, "Score (% of engine default)", legend=False
)
axes[0].set_title("(a) Speedometer 3.1", loc="left", pad=3)
axes[1].set_title("(b) Octane 2.0", loc="left", pad=3)

fig.legend(
    speedometer_handles.patches,
    [bar["label"] for bar in speedometer_bars],
    loc="upper center",
    bbox_to_anchor=(0.5, 0.995),
    ncol=2,
    frameon=False,
    handlelength=1.0,
    handleheight=0.8,
    handletextpad=0.35,
    columnspacing=0.8,
    borderpad=0.0,
    fontsize=FONT_SIZES["legend"],
)
fig.subplots_adjust(left=0.055, right=0.98, bottom=0.105, top=0.80, hspace=0.66)
save_png_and_pdf(fig, (Path(sys.argv[1]) / "performance-retained.pdf"))
