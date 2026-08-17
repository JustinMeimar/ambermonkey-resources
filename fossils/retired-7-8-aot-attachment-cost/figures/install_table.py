#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Single table: one row per AOT artifact class, columns for install
vs compile cost, per-process call counts, and per-process image bytes.

Each row is a direct AOT-vs-runtime comparison of the *same* artifact
class, using the same clock and the same cpstartup workload. Ion status
is symmetric between cells so it cancels out of the compile column."""

import sys
from pathlib import Path

from fossil_figures import load_stdin, write_typst_table


ROWS = (
    ("interpreter", "baseline interpreter"),
    ("baseline_scripts", "baseline scripts"),
    ("ic_stubs", "IC stubs"),
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
    if set(data.columns) != {"blocked"}:
        raise SystemExit(f"expected only blocked, found {sorted(data.columns)}")
    metric = data.columns["blocked"]

    rows = []
    for key, label in ROWS:
        install_us = scalar(metric, "artifacts", key, "install_us_per_call")
        compile_us = scalar(metric, "artifacts", key, "compile_us_per_call")
        installs = scalar(metric, "artifacts", key, "installs_per_proc")
        compiles = scalar(metric, "artifacts", key, "compiles_per_proc")
        image_bytes = scalar(metric, "artifacts", key, "image_bytes_per_proc")
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
            {"key": "artifact",         "label": "artifact",              "align": "left",  "format": "str"},
            {"key": "installs_per_proc","label": "AOT installs / proc",   "align": "right", "format": "float"},
            {"key": "compiles_per_proc","label": "runtime compiles / proc","align": "right", "format": "float"},
            {"key": "install_us",       "label": "install (μs / call)",   "align": "right", "format": "float"},
            {"key": "compile_us",       "label": "compile (μs / call)",   "align": "right", "format": "float"},
            {"key": "speedup",          "label": "compile / install",     "align": "right", "format": "float"},
            {"key": "image_kb_per_proc","label": "image (KB / proc)",     "align": "right", "format": "float"},
        ],
        rows=rows,
    )


if __name__ == "__main__":
    main()
