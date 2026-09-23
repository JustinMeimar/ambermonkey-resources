from fossil_figures import Scalar


VARIANTS = ("baseline-jit", "am-rit", "am-rit-nl", "am-rit-nl-vm")
TARGETED_BENCHES = (
    "interrupt-check",
    "stack-check",
    "stack-abi-call",
    "prebarrier",
    "prebarrier-abi-call",
    "vm-call",
    "abi-call",
)
CONTROL_BENCHES = ("arith", "prop-load", "array-load")
BENCHES = TARGETED_BENCHES + CONTROL_BENCHES
BENCH_LABELS = {
    "interrupt-check": "Interrupt",
    "stack-check": "Stack",
    "stack-abi-call": "Stack + ABI",
    "prebarrier": "Pre-barrier",
    "prebarrier-abi-call": "Pre-barrier + ABI",
    "vm-call": "VM call",
    "abi-call": "ABI call",
    "arith": "Arithmetic",
    "prop-load": "Property load",
    "array-load": "Array load",
}
VARIANT_LABELS = {
    "baseline-jit": "Baseline JIT",
    "am-rit": "RIT",
    "am-rit-nl": "RIT + Native-Linker",
    "am-rit-nl-vm": "RIT + Native-Linker + Value Mirroring",
}
CONFIG_FOR_VARIANT = {
    "baseline-jit": "default-no-ion",
    "am-rit": "aot",
    "am-rit-nl": "aot-corpus-ic",
    "am-rit-nl-vm": "aot-corpus",
}


def validate_variants(data):
    present = set(data.column_names)
    expected = set(VARIANTS)
    if present != expected:
        raise ValueError(
            f"variant mismatch: missing={sorted(expected - present)}, "
            f"unexpected={sorted(present - expected)}"
        )


def metric_cells(data, metric):
    validate_variants(data)
    table = data.flat_table()
    cells: dict[str, dict[str, Scalar]] = {}
    for bench in BENCHES:
        path = f"benchmarks.{bench}.{metric}"
        cells[bench] = {}
        for variant in VARIANTS:
            value = table[variant].get(path)
            if value is None:
                raise ValueError(f"{variant}: missing metric {path}")
            cells[bench][variant] = value
    return cells
