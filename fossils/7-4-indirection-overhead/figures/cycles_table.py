#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Emit paper-ready per-benchmark values and aggregate ratios as JSON."""

import json
import math
import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


BUILDS = ("default", "opt", "no-opt")
BENCHES = (
    "interrupt-check",
    "stack-check",
    "prebarrier",
    "vm-call",
    "abi-call",
    "arith",
    "prop-load",
    "array-load",
)
TARGETED_BENCHES = BENCHES[:5]
CONTROL_BENCHES = BENCHES[5:]
METRIC = "cycles_per_iter"
INSNS_METRIC = "insns_per_iter"
IPC_METRIC = "ipc"

CPI_COLUMNS = {
    "default": {
        "key": "runtime_baseline_cpi",
        "label": "runtime Baseline cyc/it",
        "align": "right",
        "format": "float",
    },
    "opt": {
        "key": "aot_baseline_cpi",
        "label": "AOT Baseline cyc/it",
        "align": "right",
        "format": "float",
    },
    "no-opt": {
        "key": "aot_no_opt_cpi",
        "label": "AOT no-opt cyc/it",
        "align": "right",
        "format": "float",
    },
}

INSNS_COLUMNS = {
    "default": {
        "key": "runtime_baseline_ipi",
        "label": "runtime Baseline ins/it",
        "align": "right",
        "format": "float",
    },
    "opt": {
        "key": "aot_baseline_ipi",
        "label": "AOT Baseline ins/it",
        "align": "right",
        "format": "float",
    },
    "no-opt": {
        "key": "aot_no_opt_ipi",
        "label": "AOT no-opt ins/it",
        "align": "right",
        "format": "float",
    },
}

IPC_COLUMNS = {
    "default": {
        "key": "runtime_baseline_ipc",
        "label": "runtime Baseline IPC",
        "align": "right",
        "format": "float",
    },
    "opt": {
        "key": "aot_baseline_ipc",
        "label": "AOT Baseline IPC",
        "align": "right",
        "format": "float",
    },
    "no-opt": {
        "key": "aot_no_opt_ipc",
        "label": "AOT no-opt IPC",
        "align": "right",
        "format": "float",
    },
}

INSNS_OVERHEAD_COLUMNS = [
    (
        "opt",
        "default",
        {
            "key": "aot_over_runtime_ipi_overhead",
            "label": "AOT ins overhead",
            "align": "right",
            "format": "percent",
        },
    ),
]

IPC_DELTA_COLUMNS = [
    (
        "opt",
        "default",
        {
            "key": "aot_over_runtime_ipc_delta",
            "label": "AOT IPC Δ",
            "align": "right",
            "format": "percent",
        },
    ),
]

DERIVED = [
    (
        "opt",
        "default",
        {
            "key": "aot_over_runtime_cyc",
            "label": "AOT−runtime",
            "align": "right",
            "format": "float",
        },
        {
            "key": "aot_over_runtime_ratio",
            "label": "AOT/runtime",
            "align": "right",
            "format": "float",
        },
        {
            "key": "aot_over_runtime_overhead",
            "label": "AOT overhead",
            "align": "right",
            "format": "percent",
        },
    ),
    (
        "no-opt",
        "opt",
        {
            "key": "no_opt_over_opt_cyc",
            "label": "no-opt−opt",
            "align": "right",
            "format": "float",
        },
        {
            "key": "no_opt_over_opt_ratio",
            "label": "no-opt/opt",
            "align": "right",
            "format": "float",
        },
        {
            "key": "no_opt_over_opt_overhead",
            "label": "no-opt overhead",
            "align": "right",
            "format": "percent",
        },
    ),
]


def split_variant(variant):
    for build in sorted(BUILDS, key=len, reverse=True):
        suffix = "-" + build
        if variant.endswith(suffix):
            return variant[: -len(suffix)], build
    return None, None


def mean_of(table, variant, metric):
    entry = table.get(variant, {}).get(metric)
    return None if entry is None else entry.mean


def geometric_mean(values):
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires at least one positive value")
    return math.exp(math.fsum(math.log(value) for value in values) / len(values))


def main():
    data = load_stdin()
    table = data.flat_table()

    cells = {}
    insns_cells = {}
    ipc_cells = {}
    for variant in table:
        bench, build = split_variant(variant)
        if bench is None:
            continue
        mean = mean_of(table, variant, METRIC)
        if mean is not None:
            cells.setdefault(bench, {})[build] = mean
        ipi = mean_of(table, variant, INSNS_METRIC)
        if ipi is not None:
            insns_cells.setdefault(bench, {})[build] = ipi
        ipc = mean_of(table, variant, IPC_METRIC)
        if ipc is not None:
            ipc_cells.setdefault(bench, {})[build] = ipc

    if not cells:
        raise SystemExit("cycles_table: no <bench>-<build> variants with cycles_per_iter")

    benches = [bench for bench in BENCHES if bench in cells]
    benches += sorted(set(cells) - set(benches))
    # A placeholder no-opt variant currently exists for only one benchmark.
    # Emit a rectangular paper table from complete build cells and leave any
    # partial auxiliary ablation out of this primary AOT/runtime comparison.
    present_builds = [
        build for build in BUILDS if all(build in cells[bench] for bench in benches)
    ]
    if not present_builds:
        raise SystemExit("cycles_table: no build is present for every benchmark")
    present_derived = [
        derived
        for derived in DERIVED
        if derived[0] in present_builds and derived[1] in present_builds
    ]

    columns = [{"key": "bench", "label": "microbenchmark", "align": "left", "format": "str"}]
    columns += [CPI_COLUMNS[build] for build in present_builds]
    for _, _, delta_column, ratio_column, overhead_column in present_derived:
        columns += [delta_column, ratio_column, overhead_column]

    insns_present = [
        build for build in present_builds
        if all(build in insns_cells.get(bench, {}) for bench in benches)
    ]
    ipc_present = [
        build for build in present_builds
        if all(build in ipc_cells.get(bench, {}) for bench in benches)
    ]
    columns += [INSNS_COLUMNS[build] for build in insns_present]
    insns_derived = [
        (num, den, col)
        for num, den, col in INSNS_OVERHEAD_COLUMNS
        if num in insns_present and den in insns_present
    ]
    for _, _, col in insns_derived:
        columns.append(col)
    columns += [IPC_COLUMNS[build] for build in ipc_present]
    ipc_derived = [
        (num, den, col)
        for num, den, col in IPC_DELTA_COLUMNS
        if num in ipc_present and den in ipc_present
    ]
    for _, _, col in ipc_derived:
        columns.append(col)

    rows = []
    for bench in benches:
        cell = cells[bench]
        missing = [build for build in present_builds if build not in cell]
        if missing:
            raise SystemExit(
                f"cycles_table: bench {bench!r} missing builds {missing!r}; "
                "partial build coverage is not supported"
            )
        row = [bench] + [cell[build] for build in present_builds]
        for numerator, denominator, _, _, _ in present_derived:
            ratio = cell[numerator] / cell[denominator]
            row += [
                cell[numerator] - cell[denominator],
                ratio,
                ratio - 1.0,
            ]
        row += [insns_cells[bench][build] for build in insns_present]
        for num, den, _ in insns_derived:
            row.append(insns_cells[bench][num] / insns_cells[bench][den] - 1.0)
        row += [ipc_cells[bench][build] for build in ipc_present]
        for num, den, _ in ipc_derived:
            row.append(ipc_cells[bench][num] / ipc_cells[bench][den] - 1.0)
        rows.append(row)

    # Geometric means make the aggregate invariant to benchmark scale and
    # preserve the multiplicative interpretation of an overhead ratio.
    aggregate = ["Geometric mean"]
    aggregate += [geometric_mean([cells[b][build] for b in benches]) for build in present_builds]
    for numerator, denominator, _, _, _ in present_derived:
        ratio = geometric_mean(
            [cells[bench][numerator] / cells[bench][denominator] for bench in benches]
        )
        aggregate += [
            geometric_mean([cells[b][numerator] for b in benches])
            - geometric_mean([cells[b][denominator] for b in benches]),
            ratio,
            ratio - 1.0,
        ]
    aggregate += [
        geometric_mean([insns_cells[b][build] for b in benches])
        for build in insns_present
    ]
    for num, den, _ in insns_derived:
        ratio = geometric_mean(
            [insns_cells[b][num] / insns_cells[b][den] for b in benches]
        )
        aggregate.append(ratio - 1.0)
    aggregate += [
        geometric_mean([ipc_cells[b][build] for b in benches])
        for build in ipc_present
    ]
    for num, den, _ in ipc_derived:
        ratio = geometric_mean(
            [ipc_cells[b][num] / ipc_cells[b][den] for b in benches]
        )
        aggregate.append(ratio - 1.0)
    rows.append(aggregate)

    output = Path(sys.argv[1]).with_suffix(".json")
    write_typst_table(
        output,
        columns=columns,
        rows=rows,
    )

    # Keep prose-facing summary values in the same generated artifact as the
    # complete table. Typst uses these for methodological counts; measured
    # ratios continue to come from the Geometric mean row via cell-value.
    repetitions = []
    for bench in benches:
        for build in present_builds:
            value = mean_of(table, f"{bench}-{build}", "meta.iterations")
            if value is not None:
                repetitions.append(int(value))
    if repetitions and len(set(repetitions)) != 1:
        raise SystemExit(
            "cycles_table: configurations have inconsistent repetition counts: "
            f"{sorted(set(repetitions))}"
        )

    payload = json.loads(output.read_text())
    payload.update(
        {
            "benchmark_count": len(benches),
            "targeted_benchmark_count": len(set(benches) & set(TARGETED_BENCHES)),
            "control_benchmark_count": len(set(benches) & set(CONTROL_BENCHES)),
            "repetitions_per_configuration": repetitions[0] if repetitions else 1,
            "primary_metric": "user cycles per semantic loop iteration",
            "counter_events": ["cycles:u", "instructions:u", "ref-cycles:u"],
            "aggregate": "geometric mean of per-benchmark AOT/runtime ratios",
        }
    )
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
