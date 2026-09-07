#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit aggregate JetStream startup latency by execution mode."""

import os
from pathlib import Path
import statistics
import sys

from fossil_figures import load_stdin, write_typst_table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_values

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import load_configurations

CONFIGS = load_configurations()
ORDER = tuple(slug for slug, config in sorted(CONFIGS.items(), key=lambda item: item[1]["order"]))

data = load_stdin()
variants = [variant for variant in ORDER if variant in data.columns]
if not variants:
    raise SystemExit("startup_table: no known variants")
if "interp-only" not in variants:
    raise SystemExit("startup_table: missing interp-only baseline")

samples = {
    variant: run_values(data.columns[variant], "startup_geomean_ms")
    for variant in variants
}
means = {variant: statistics.fmean(values) for variant, values in samples.items()}
baseline = means["interp-only"]
rows = []
for variant in variants:
    values = samples[variant]
    rows.append(
        [
            CONFIGS[variant]["long"],
            round(means[variant], 3),
            round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
            round(means[variant] / baseline, 4),
        ]
    )

write_typst_table(
    Path(sys.argv[1]),
    columns=[
        {"key": "variant", "label": "Variant", "align": "left", "format": "str"},
        {"key": "latency_ms", "label": "First (ms)", "align": "right", "format": "float"},
        {"key": "stdev_ms", "label": "stdev", "align": "right", "format": "float"},
        {"key": "ratio_over_interp", "label": "vs interp", "align": "right", "format": "float"},
    ],
    rows=rows,
)
