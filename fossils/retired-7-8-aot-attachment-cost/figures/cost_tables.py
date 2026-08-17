#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit AOT attachment cost tables (startup timings and per-phase counters)."""

import json
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


PHASE_LABELS = (
    ("image_compatibility", "image compatibility"),
    ("interpreter_attach", "interpreter attachment"),
    ("rit_initialization", "indirection-table initialization"),
    ("ic_corpus_attach", "IC corpus attachment"),
    ("baseline_function_lookup", "Baseline-function lookup"),
    ("baseline_function_reconstruct", "Baseline metadata reconstruction"),
    ("ic_image_lookup", "IC image lookup"),
    ("ic_private_attach", "private IC-stub attachment"),
    ("runtime_baseline_compile", "runtime Baseline compilation"),
    ("runtime_ic_compile", "runtime IC compilation"),
)
COUNTER_LABELS = (
    ("interpreter_wrappers", "interpreter wrappers", "count/process"),
    ("interpreter_metadata_bytes", "interpreter metadata", "bytes/process"),
    ("ic_corpus_wrappers", "IC corpus wrappers", "count/process"),
    ("ic_corpus_metadata_bytes", "IC corpus metadata", "bytes/process"),
    ("baseline_lookup_hits", "Baseline lookup hits", "count/process"),
    ("baseline_lookup_misses", "Baseline lookup misses", "count/process"),
    ("baseline_wrappers", "Baseline wrappers", "count/process"),
    ("baseline_metadata_bytes", "Baseline metadata", "bytes/process"),
    ("ic_image_lookup_hits", "IC image lookup hits", "count/process"),
    ("ic_image_lookup_misses", "IC image lookup misses", "count/process"),
    ("ic_private_stubs", "private IC stubs", "count/process"),
    ("ic_private_stub_bytes", "private IC-stub storage", "bytes/process"),
)


def child(metric, path):
    current = metric
    for key in path.split("."):
        current = current.children[key]
    return current.scalar.mean, current.scalar.stddev


def main():
    data = load_stdin()
    if set(data.columns) != {"blocked"}:
        raise SystemExit(f"expected only blocked, found {sorted(data.columns)}")
    metric = data.columns["blocked"]
    output = Path(sys.argv[1]).with_suffix(".json")

    startup_rows = []
    for label, clean, timed, overhead in (
        ("runtime generated", "runtime_clean", "runtime_timed", "runtime"),
        ("AOT image", "aot_clean", "aot_timed", "aot"),
    ):
        clean_mean, clean_sd = child(metric, f"startup_ms.{clean}")
        timed_mean, timed_sd = child(metric, f"startup_ms.{timed}")
        overhead_mean, overhead_sd = child(metric, f"timing_overhead_ms.{overhead}")
        startup_rows.append(
            [label, clean_mean, clean_sd, timed_mean, timed_sd, overhead_mean, overhead_sd]
        )
    write_typst_table(
        output.with_name("startup-effects.json"),
        columns=[
            {"key": "mode", "label": "delivery mode"},
            {"key": "clean_mean_ms", "label": "clean mean (ms)", "format": "float", "align": "right"},
            {"key": "clean_sd_ms", "label": "clean SD (ms)", "format": "float", "align": "right"},
            {"key": "timed_mean_ms", "label": "timed mean (ms)", "format": "float", "align": "right"},
            {"key": "timed_sd_ms", "label": "timed SD (ms)", "format": "float", "align": "right"},
            {"key": "overhead_mean_ms", "label": "timing overhead (ms)", "format": "float", "align": "right"},
            {"key": "overhead_sd_ms", "label": "overhead SD (ms)", "format": "float", "align": "right"},
        ],
        rows=startup_rows,
    )

    phase_rows = []
    for key, label in PHASE_LABELS:
        runtime_mean, runtime_sd = child(metric, f"phases_ms_per_process.runtime.{key}")
        aot_mean, aot_sd = child(metric, f"phases_ms_per_process.aot.{key}")
        phase_rows.append([label, runtime_mean, runtime_sd, aot_mean, aot_sd])
    write_typst_table(
        output,
        columns=[
            {"key": "phase", "label": "phase"},
            {"key": "runtime_mean_ms", "label": "runtime mean (ms/process)", "format": "float", "align": "right"},
            {"key": "runtime_sd_ms", "label": "runtime SD", "format": "float", "align": "right"},
            {"key": "aot_mean_ms", "label": "AOT mean (ms/process)", "format": "float", "align": "right"},
            {"key": "aot_sd_ms", "label": "AOT SD", "format": "float", "align": "right"},
        ],
        rows=phase_rows,
    )

    counter_rows = []
    for key, label, unit in COUNTER_LABELS:
        runtime_mean, runtime_sd = child(metric, f"counters_per_process.runtime.{key}")
        aot_mean, aot_sd = child(metric, f"counters_per_process.aot.{key}")
        counter_rows.append([label, unit, runtime_mean, runtime_sd, aot_mean, aot_sd])
    write_typst_table(
        output.with_name("attachment-counts.json"),
        columns=[
            {"key": "counter", "label": "counter"},
            {"key": "unit", "label": "unit"},
            {"key": "runtime_mean", "label": "runtime mean", "format": "float", "align": "right"},
            {"key": "runtime_sd", "label": "runtime SD", "format": "float", "align": "right"},
            {"key": "aot_mean", "label": "AOT mean", "format": "float", "align": "right"},
            {"key": "aot_sd", "label": "AOT SD", "format": "float", "align": "right"},
        ],
        rows=counter_rows,
    )

    summary = json.loads(output.read_text())
    effect_mean, effect_sd = child(metric, "startup_effect_ms")
    ratio_mean, ratio_sd = child(metric, "startup_effect_ratio")
    summary.update(
        {
            "paired_startup_effect_ms": {"mean": effect_mean, "stddev": effect_sd},
            "paired_startup_ratio": {"mean": ratio_mean, "stddev": ratio_sd},
            "blocks": int(child(metric, "meta.iterations")[0]),
        }
    )
    output.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
