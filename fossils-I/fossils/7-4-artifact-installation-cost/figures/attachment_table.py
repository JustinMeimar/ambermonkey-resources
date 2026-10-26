#!/usr/bin/env python3
"""Compare per-artifact installation costs with run-time compilation costs.

The matched variants use the same clock and cpstartup workload, so the
per-call columns are directly comparable."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))


from figure_data import parse_data, table_json

ROWS = (
    ("interpreter", "interpreter"),
    ("baseline_scripts", "self-hosted"),
    ("ic_stubs", "IC stubs"),
)
AOT_VARIANTS = (
    ("aot-corpus-ic", "AmberMonkey-IC"),
    ("aot-corpus", "AmberMonkey"),
)
BASELINE = "default-no-ion"


def scalar(metric, *path):
    m = metric
    for key in path:
        if m.children is None or key not in m.children:
            return 0.0
        m = m.children[key]
    return m.scalar.mean if m.scalar else 0.0


def main():
    data = parse_data(json.load(sys.stdin))
    if BASELINE not in data.columns:
        raise SystemExit(
            f"missing column {BASELINE!r}; found {sorted(data.columns)}"
        )
    candidates = [item for item in AOT_VARIANTS if item[0] in data.columns]
    runtime = data.columns[BASELINE]

    rows = []
    if not candidates:
        for key, artifact_label in ROWS:
            compiles = scalar(runtime, 'artifacts', key, 'compiles_per_proc')
            if compiles:
                rows.append(['Baseline JIT', artifact_label, 0, round(compiles, 2),
                             None, round(scalar(runtime, 'artifacts', key,
                                                'compile_us_per_call'), 2), None])
    for variant, variant_label in candidates:
        aot = data.columns[variant]
        for key, artifact_label in ROWS:
            install_us = scalar(aot, "artifacts", key, "install_us_per_call")
            installs = scalar(aot, "artifacts", key, "installs_per_proc")
            if not installs:
                continue
            compile_us = scalar(
                runtime, "artifacts", key, "compile_us_per_call"
            )
            compiles = scalar(runtime, "artifacts", key, "compiles_per_proc")
            rows.append(
                [
                    variant_label,
                    artifact_label,
                    round(installs, 2),
                    round(compiles, 2),
                    round(install_us, 2),
                    round(compile_us, 2),
                    round(compile_us / install_us, 2) if install_us else None,
                ]
            )

    (Path(sys.argv[1]) / "attachment.json").write_text(table_json(
        columns=[
            {
                "key": "variant",
                "label": "configuration",
                "align": "left",
                "format": "str",
            },
            {
                "key": "artifact",
                "label": "artifact",
                "align": "left",
                "format": "str",
            },
            {
                "key": "installs_per_proc",
                "label": "installs/proc",
                "align": "right",
                "format": "float",
            },
            {
                "key": "compiles_per_proc",
                "label": "compiles/proc",
                "align": "right",
                "format": "float",
            },
            {
                "key": "install_us",
                "label": "µs/install",
                "align": "right",
                "format": "float",
            },
            {
                "key": "compile_us",
                "label": "µs/compile",
                "align": "right",
                "format": "float",
            },
            {
                "key": "speedup",
                "label": "ratio",
                "align": "right",
                "format": "float",
            },
        ],
        rows=rows,
    ))


if __name__ == "__main__":
    main()
