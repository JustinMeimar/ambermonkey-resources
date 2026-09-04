#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit the AmberMonkey indirection-ablation metrics as table JSON."""

import json
import math
from pathlib import Path
import sys

from fossil_figures import load_stdin, write_typst_table

from common import BENCHES, VARIANTS, metric_cells


VARIANT_KEYS = {
    "baseline-jit": "baseline_jit",
    "am-rit": "rit",
    "am-rit-nl": "native_linker",
    "am-rit-nl-vm": "value_mirror",
}
VARIANT_LABELS = {
    "baseline-jit": "Baseline JIT",
    "am-rit": "RIT",
    "am-rit-nl": "RIT + NL",
    "am-rit-nl-vm": "RIT + NL + VM",
}
COMPARISONS = (
    ("rit_over_baseline", "am-rit", "baseline-jit", "RIT / baseline"),
    ("native_linker_over_rit", "am-rit-nl", "am-rit", "NL / RIT"),
    (
        "value_mirror_over_native_linker",
        "am-rit-nl-vm",
        "am-rit-nl",
        "VM / NL",
    ),
    ("full_over_baseline", "am-rit-nl-vm", "baseline-jit", "Full / baseline"),
)


def geometric_mean(values):
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(math.fsum(math.log(value) for value in values) / len(values))


def ratio(values, numerator, denominator):
    return values[numerator] / values[denominator]


def comparison_columns(suffix, label_suffix, value_format):
    return [
        {
            "key": f"{key}_{suffix}",
            "label": f"{label} {label_suffix}",
            "align": "right",
            "format": value_format,
        }
        for key, _, _, label in COMPARISONS
    ]


def main():
    data = load_stdin()
    cycles = metric_cells(data, "cycles_per_iter")
    instructions = metric_cells(data, "insns_per_iter")
    ipc = metric_cells(data, "ipc")

    columns = [
        {"key": "bench", "label": "microbenchmark", "align": "left", "format": "str"}
    ]
    columns += [
        {
            "key": f"{VARIANT_KEYS[variant]}_cpi",
            "label": f"{VARIANT_LABELS[variant]} cyc/it",
            "align": "right",
            "format": "float",
        }
        for variant in VARIANTS
    ]
    columns += comparison_columns("cycles", "cycles", "float")
    columns += comparison_columns("ratio", "ratio", "float")
    columns += comparison_columns("overhead", "overhead", "percent")
    columns += comparison_columns("ipi_overhead", "instruction overhead", "percent")
    columns += comparison_columns("ipc_delta", "IPC delta", "percent")

    rows = []
    for bench in BENCHES:
        cycle_values = {
            variant: cycles[bench][variant].mean for variant in VARIANTS
        }
        instruction_values = {
            variant: instructions[bench][variant].mean for variant in VARIANTS
        }
        ipc_values = {variant: ipc[bench][variant].mean for variant in VARIANTS}
        cycle_ratios = [
            ratio(cycle_values, numerator, denominator)
            for _, numerator, denominator, _ in COMPARISONS
        ]
        rows.append(
            [bench]
            + [cycle_values[variant] for variant in VARIANTS]
            + [
                cycle_values[numerator] - cycle_values[denominator]
                for _, numerator, denominator, _ in COMPARISONS
            ]
            + cycle_ratios
            + [value - 1.0 for value in cycle_ratios]
            + [
                ratio(instruction_values, numerator, denominator) - 1.0
                for _, numerator, denominator, _ in COMPARISONS
            ]
            + [
                ratio(ipc_values, numerator, denominator) - 1.0
                for _, numerator, denominator, _ in COMPARISONS
            ]
        )

    cycle_geomeans = {
        variant: geometric_mean(
            [cycles[bench][variant].mean for bench in BENCHES]
        )
        for variant in VARIANTS
    }
    aggregate_ratios = [
        geometric_mean(
            [
                cycles[bench][numerator].mean / cycles[bench][denominator].mean
                for bench in BENCHES
            ]
        )
        for _, numerator, denominator, _ in COMPARISONS
    ]
    aggregate = ["Geometric mean"]
    aggregate += [cycle_geomeans[variant] for variant in VARIANTS]
    aggregate += [
        cycle_geomeans[numerator] - cycle_geomeans[denominator]
        for _, numerator, denominator, _ in COMPARISONS
    ]
    aggregate += aggregate_ratios
    aggregate += [value - 1.0 for value in aggregate_ratios]
    for metric in (instructions, ipc):
        aggregate += [
            geometric_mean(
                [
                    metric[bench][numerator].mean
                    / metric[bench][denominator].mean
                    for bench in BENCHES
                ]
            )
            - 1.0
            for _, numerator, denominator, _ in COMPARISONS
        ]
    rows.append(aggregate)

    output = Path(sys.argv[1])
    write_typst_table(output, columns=columns, rows=rows)

    table = data.flat_table()
    repetitions = {
        int(table[variant]["meta.iterations"].mean) for variant in VARIANTS
    }
    if len(repetitions) != 1:
        raise ValueError(f"inconsistent repetition counts: {sorted(repetitions)}")

    payload = json.loads(output.read_text())
    payload.update(
        {
            "benchmark_count": len(BENCHES),
            "repetitions_per_configuration": repetitions.pop(),
            "primary_metric": "user cycles per semantic loop iteration",
            "counter_events": ["cycles:u", "instructions:u", "ref-cycles:u"],
            "aggregate": "geometric mean of per-benchmark ratios",
        }
    )
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
