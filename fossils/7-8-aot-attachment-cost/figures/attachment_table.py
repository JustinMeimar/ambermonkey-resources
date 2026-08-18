#!/home/justin/tools/fossil/figures/.venv/bin/python
"""One row per AOT artifact class: install cost from the aot cell, compile
cost from the runtime cell, and the AOT image contribution per process.

Same clock, same cpstartup workload, so the per-call columns are a direct
AOT-vs-runtime comparison per artifact class."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table

ROWS = (
    ("interpreter",      "baseline interpreter"),
    ("baseline_scripts", "baseline scripts"),
    ("ic_stubs",         "IC stubs"),
)


def scalar(metric, *path):
    m = metric
    for key in path:
        if m.children is None or key not in m.children:
            return 0.0
        m = m.children[key]
    return m.scalar.mean if m.scalar else 0.0


def main():
    data = load_stdin()
    for name in ("runtime", "aot"):
        if name not in data.columns:
            raise SystemExit(f"missing column {name!r}; found {sorted(data.columns)}")
    runtime = data.columns["runtime"]
    aot = data.columns["aot"]

    rows = []
    for key, label in ROWS:
        install_us  = scalar(aot,     "artifacts", key, "install_us_per_call")
        compile_us  = scalar(runtime, "artifacts", key, "compile_us_per_call")
        installs    = scalar(aot,     "artifacts", key, "installs_per_proc")
        compiles    = scalar(runtime, "artifacts", key, "compiles_per_proc")
        image_bytes = scalar(aot,     "artifacts", key, "image_bytes_per_proc")
        speedup = (compile_us / install_us) if install_us > 0 else 0.0
        rows.append([
            label,
            round(installs, 2),
            round(compiles, 2),
            round(install_us, 2),
            round(compile_us, 2),
            round(speedup, 2),
            round(image_bytes / 1024.0, 2),
        ])

    write_typst_table(
        Path(sys.argv[1]),
        columns=[
            {"key": "artifact",          "label": "artifact",                "align": "left",  "format": "str"},
            {"key": "installs_per_proc", "label": "AOT installs / proc",     "align": "right", "format": "float"},
            {"key": "compiles_per_proc", "label": "runtime compiles / proc", "align": "right", "format": "float"},
            {"key": "install_us",        "label": "install (us / call)",     "align": "right", "format": "float"},
            {"key": "compile_us",        "label": "compile (us / call)",     "align": "right", "format": "float"},
            {"key": "speedup",           "label": "compile / install",       "align": "right", "format": "float"},
            {"key": "image_kb_per_proc", "label": "image (KB / proc)",       "align": "right", "format": "float"},
        ],
        rows=rows,
    )


if __name__ == "__main__":
    main()
