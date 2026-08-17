#!/usr/bin/env python3
"""Bypass table script: reads records/ directly, tolerates empty perf observations.
The strict pipeline (parse_cycles.py -> cycles_table.py) refuses on any empty stdout;
some legacy records have such gaps. Output shape mirrors cycles_table.py."""

import json
import math
import os
import statistics
import sys
from pathlib import Path

RECORDS_DIR = Path(__file__).parent.parent / "records"

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

ITER_COUNTS = {
    "interrupt-check": 10_000_000_000,
    "stack-check":     500_000_000,
    "prebarrier":      500_000_000,
    "vm-call":         20_000_000,
    "abi-call":        100_000_000,
    "arith":           100_000_000,
    "prop-load":       100_000_000,
    "array-load":      100_000_000,
}
REQUIRED_EVENTS = ("cycles:u", "instructions:u", "ref-cycles:u")
MIN_RUNNING = 99.5

CPI_LABELS = {
    "default": ("runtime_baseline_cpi", "runtime Baseline cyc/it"),
    "opt":     ("aot_baseline_cpi",     "AOT Baseline cyc/it"),
    "no-opt":  ("aot_no_opt_cpi",       "AOT no-opt cyc/it"),
}
IPI_LABELS = {
    "default": ("runtime_baseline_ipi", "runtime Baseline ins/it"),
    "opt":     ("aot_baseline_ipi",     "AOT Baseline ins/it"),
    "no-opt":  ("aot_no_opt_ipi",       "AOT no-opt ins/it"),
}
IPC_LABELS = {
    "default": ("runtime_baseline_ipc", "runtime Baseline IPC"),
    "opt":     ("aot_baseline_ipc",     "AOT Baseline IPC"),
    "no-opt":  ("aot_no_opt_ipc",       "AOT no-opt IPC"),
}


def split_variant(variant):
    for build in sorted(BUILDS, key=len, reverse=True):
        suffix = "-" + build
        if variant.endswith(suffix):
            return variant[: -len(suffix)], build
    return None, None


def parse_perf_ndjson(text):
    events = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = obj.get("event")
        val = obj.get("counter-value")
        if event is None or val is None:
            continue
        try:
            value = float(val)
        except (TypeError, ValueError):
            return None
        try:
            pcnt_running = float(obj.get("pcnt-running", 0.0))
        except (TypeError, ValueError):
            pcnt_running = 0.0
        events[event] = {"value": value, "pcnt_running": pcnt_running}
    return events


def observation_metrics(stdout_text, iter_count):
    events = parse_perf_ndjson(stdout_text)
    if events is None:
        return None
    for req in REQUIRED_EVENTS:
        if req not in events:
            return None
        if events[req]["pcnt_running"] < MIN_RUNNING:
            return None
    cycles = events["cycles:u"]["value"]
    insns = events["instructions:u"]["value"]
    return {
        "cycles_per_iter": cycles / iter_count,
        "insns_per_iter":  insns / iter_count,
        "ipc":             (insns / cycles) if cycles else 0.0,
    }


def observation_stdout(obs):
    s = obs.get("stdout", "")
    if isinstance(s, list):
        s = "\n".join(s)
    if not isinstance(s, str):
        return ""
    return s


def collect(records_dir):
    """Group per-variant metric samples across all records/.

    Returns (samples_by_variant, iteration_counts_by_variant,
    empty_count, skipped_count). Each sample is a metric dict.
    """
    samples = {}
    iters = {}
    empty = 0
    skipped = 0

    if not records_dir.is_dir():
        return samples, iters, empty, skipped

    for record in sorted(records_dir.iterdir()):
        manifest_path = record / "manifest.json"
        results_path = record / "results.json"
        if not manifest_path.is_file() or not results_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
            results = json.loads(results_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        variant = manifest.get("variant")
        bench, _ = split_variant(variant or "")
        if bench is None or bench not in ITER_COUNTS:
            continue
        iter_count = ITER_COUNTS[bench]
        iterations = manifest.get("iterations")
        if isinstance(iterations, int):
            iters.setdefault(variant, []).append(iterations)
        for obs in results.get("observations", []):
            if int(obs.get("exit_code", 1)) != 0:
                skipped += 1
                continue
            text = observation_stdout(obs)
            if not text.strip():
                empty += 1
                continue
            metrics = observation_metrics(text, iter_count)
            if metrics is None:
                skipped += 1
                continue
            samples.setdefault(variant, []).append(metrics)
    return samples, iters, empty, skipped


def mean(values):
    return statistics.fmean(values) if values else None


def variant_means(samples):
    """Latest-record semantics: use samples across all records/, mean per metric."""
    out = {}
    for variant, obs_list in samples.items():
        if not obs_list:
            continue
        out[variant] = {
            "cycles_per_iter": mean([o["cycles_per_iter"] for o in obs_list]),
            "insns_per_iter":  mean([o["insns_per_iter"]  for o in obs_list]),
            "ipc":             mean([o["ipc"]             for o in obs_list]),
            "n":               len(obs_list),
        }
    return out


def geometric_mean(values):
    if not values or any(v <= 0 for v in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(math.fsum(math.log(v) for v in values) / len(values))


def build_columns(present_builds, present_derived, insns_present, ipc_present, insns_derived, ipc_derived):
    columns = [{"key": "bench", "label": "microbenchmark", "align": "left", "format": "str"}]
    for build in present_builds:
        key, label = CPI_LABELS[build]
        columns.append({"key": key, "label": label, "align": "right", "format": "float"})
    for num, den in present_derived:
        columns.append({"key": f"{num}_over_{den}_cyc",      "label": f"{num}−{den}",       "align": "right", "format": "float"})
        columns.append({"key": f"{num}_over_{den}_ratio",    "label": f"{num}/{den}",       "align": "right", "format": "float"})
        columns.append({"key": f"{num}_over_{den}_overhead", "label": f"{num} overhead",    "align": "right", "format": "percent"})
    for build in insns_present:
        key, label = IPI_LABELS[build]
        columns.append({"key": key, "label": label, "align": "right", "format": "float"})
    for num, den in insns_derived:
        columns.append({"key": f"{num}_over_{den}_ipi_overhead", "label": f"{num} ins overhead", "align": "right", "format": "percent"})
    for build in ipc_present:
        key, label = IPC_LABELS[build]
        columns.append({"key": key, "label": label, "align": "right", "format": "float"})
    for num, den in ipc_derived:
        columns.append({"key": f"{num}_over_{den}_ipc_delta", "label": f"{num} IPC Δ", "align": "right", "format": "percent"})
    # Rename the primary AOT/runtime derived triple to the historical keys
    # so the paper's constants layer can still look them up by name.
    for i, col in enumerate(columns):
        col["key"] = {
            "opt_over_default_cyc":      "aot_over_runtime_cyc",
            "opt_over_default_ratio":    "aot_over_runtime_ratio",
            "opt_over_default_overhead": "aot_over_runtime_overhead",
            "opt_over_default_ipi_overhead": "aot_over_runtime_ipi_overhead",
            "opt_over_default_ipc_delta":    "aot_over_runtime_ipc_delta",
        }.get(col["key"], col["key"])
    return columns


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    samples, iters, empty, skipped = collect(RECORDS_DIR)
    means = variant_means(samples)
    if not means:
        sys.exit("emit_cycles_table: no usable observations in records/")

    cells = {}
    insns_cells = {}
    ipc_cells = {}
    for variant, m in means.items():
        bench, build = split_variant(variant)
        if bench is None:
            continue
        if m["cycles_per_iter"] is not None:
            cells.setdefault(bench, {})[build] = m["cycles_per_iter"]
        if m["insns_per_iter"] is not None:
            insns_cells.setdefault(bench, {})[build] = m["insns_per_iter"]
        if m["ipc"] is not None:
            ipc_cells.setdefault(bench, {})[build] = m["ipc"]

    benches = [b for b in BENCHES if b in cells]
    benches += sorted(set(cells) - set(benches))

    present_builds = [b for b in BUILDS if all(b in cells[bench] for bench in benches)]
    if not present_builds:
        # Fall back: pick per-bench-present builds; drop benches missing any of them
        present_builds = [b for b in BUILDS if any(b in cells[bench] for bench in benches)]
        benches = [bench for bench in benches if all(b in cells[bench] for b in present_builds)]
        if not benches:
            sys.exit("emit_cycles_table: no build is present for every benchmark and no fallback found")

    present_derived = []
    for num, den in [("opt", "default"), ("no-opt", "opt")]:
        if num in present_builds and den in present_builds:
            present_derived.append((num, den))

    insns_present = [b for b in present_builds if all(b in insns_cells.get(bench, {}) for bench in benches)]
    ipc_present = [b for b in present_builds if all(b in ipc_cells.get(bench, {}) for bench in benches)]
    insns_derived = [(n, d) for n, d in [("opt", "default")] if n in insns_present and d in insns_present]
    ipc_derived = [(n, d) for n, d in [("opt", "default")] if n in ipc_present and d in ipc_present]

    columns = build_columns(present_builds, present_derived, insns_present, ipc_present, insns_derived, ipc_derived)

    rows = []
    for bench in benches:
        cell = cells[bench]
        row = [bench] + [cell[b] for b in present_builds]
        for num, den in present_derived:
            r = cell[num] / cell[den]
            row += [cell[num] - cell[den], r, r - 1.0]
        row += [insns_cells[bench][b] for b in insns_present]
        for num, den in insns_derived:
            row.append(insns_cells[bench][num] / insns_cells[bench][den] - 1.0)
        row += [ipc_cells[bench][b] for b in ipc_present]
        for num, den in ipc_derived:
            row.append(ipc_cells[bench][num] / ipc_cells[bench][den] - 1.0)
        rows.append(row)

    aggregate = ["Geometric mean"]
    aggregate += [geometric_mean([cells[b][build] for b in benches]) for build in present_builds]
    for num, den in present_derived:
        r = geometric_mean([cells[bench][num] / cells[bench][den] for bench in benches])
        aggregate += [
            geometric_mean([cells[b][num] for b in benches]) - geometric_mean([cells[b][den] for b in benches]),
            r,
            r - 1.0,
        ]
    aggregate += [geometric_mean([insns_cells[b][build] for b in benches]) for build in insns_present]
    for num, den in insns_derived:
        r = geometric_mean([insns_cells[b][num] / insns_cells[b][den] for b in benches])
        aggregate.append(r - 1.0)
    aggregate += [geometric_mean([ipc_cells[b][build] for b in benches]) for build in ipc_present]
    for num, den in ipc_derived:
        r = geometric_mean([ipc_cells[b][num] / ipc_cells[b][den] for b in benches])
        aggregate.append(r - 1.0)
    rows.append(aggregate)

    # Some old records used iterations=1 or 2 while current runs use 10;
    # pick the maximum so the "repetitions_per_configuration" scalar the
    # paper reads reflects the latest measurement design rather than the
    # legacy shorter runs, and keep the full list under a distinct key for
    # anyone who cares about the historical variance.
    all_reps = [n for vs in iters.values() for n in vs]
    repetitions_scalar = max(all_reps) if all_reps else 1
    repetitions_observed = sorted(set(all_reps))

    output = {
        "columns": columns,
        "rows": rows,
        "benchmark_count": len(benches),
        "targeted_benchmark_count": len(set(benches) & set(TARGETED_BENCHES)),
        "control_benchmark_count": len(set(benches) & set(CONTROL_BENCHES)),
        "repetitions_per_configuration": repetitions_scalar,
        "repetitions_observed": repetitions_observed,
        "primary_metric": "user cycles per semantic loop iteration",
        "counter_events": list(REQUIRED_EVENTS),
        "aggregate": "geometric mean of per-benchmark AOT/runtime ratios",
        "samples_per_variant": {v: means[v]["n"] for v in sorted(means)},
        "empty_observations": empty,
        "skipped_observations": skipped,
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
