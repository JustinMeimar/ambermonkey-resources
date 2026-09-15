#!/usr/bin/env python3
"""Octane 2 performance retained as a fraction of each engine's default."""

import os
from pathlib import Path
import sys

import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ["FOSSIL_PROJECT_DIR"])
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import apply_amber_style, load_configurations  # noqa: E402
from benchmark_stats import bootstrap_ratio_ci  # noqa: E402

from common import load_sm_octane, run_scores, save_png_and_pdf  # noqa: E402
from reclamation_plot import render_reclamation_bars  # noqa: E402


SM_IC = "aot-corpus-ic"
SM_AM = "aot-corpus"
SM_ORACLE = "octane-am-oracle"
SM_BASELINE = "default-no-ion"
V8_DEFAULT = "octane-v8-default"
V8_JITLESS = "octane-v8-jitless"
CONFIGS = load_configurations()

LABELS = {
    SM_IC: "AM-IC",
    SM_AM: "AM",
    SM_ORACLE: "AM-Oracle",
    SM_BASELINE: "Baseline JIT",
    V8_JITLESS: "V8 Jitless",
}
COLORS = {
    SM_IC: CONFIGS[SM_IC]["color"],
    SM_AM: CONFIGS[SM_AM]["color"],
    SM_ORACLE: CONFIGS["aot-oracle"]["color"],
    SM_BASELINE: CONFIGS[SM_BASELINE]["color"],
    V8_JITLESS: CONFIGS["v8-jitless"]["color"],
}


def ratio_bar(slug, scores, default_scores, rng):
    ratio, lower_error, upper_error = bootstrap_ratio_ci(
        scores, default_scores, rng
    )
    return {
        "slug": slug,
        "ratio": ratio,
        "lower_error": lower_error,
        "upper_error": upper_error,
        "label": LABELS[slug],
        "color": COLORS[slug],
        "hatch": "///" if slug == SM_BASELINE else "",
    }


apply_amber_style("single")
data = load_stdin()
missing = [variant for variant in (V8_DEFAULT, V8_JITLESS) if variant not in data.columns]
if missing:
    raise ValueError(
        f"bury the missing Octane V8 variants before rendering: {missing}"
    )

sm = load_sm_octane()
rng = np.random.default_rng(0)
bars = [
    ratio_bar(SM_IC, sm[SM_IC], sm["default"], rng),
    ratio_bar(SM_AM, sm[SM_AM], sm["default"], rng),
]
if SM_ORACLE in data.columns:
    bars.append(
        ratio_bar(SM_ORACLE, run_scores(data.columns[SM_ORACLE]), sm["default"], rng)
    )
bars.extend(
    [
        ratio_bar(SM_BASELINE, sm[SM_BASELINE], sm["default"], rng),
        ratio_bar(
            V8_JITLESS,
            run_scores(data.columns[V8_JITLESS]),
            run_scores(data.columns[V8_DEFAULT]),
            rng,
        ),
    ]
)

render_reclamation_bars(
    bars,
    "Octane 2.0 score (% of engine default)",
    save_png_and_pdf,
    sys.argv[1],
)
