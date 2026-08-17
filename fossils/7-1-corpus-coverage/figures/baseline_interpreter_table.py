#!/usr/bin/env python3
"""Baseline-interpreter coverage table."""

import json
import pathlib
import sys

from _common import (
    COLUMN_ORDER, COLUMN_LABELS, dig, die, fmt_scalar,
)


def main():
    data = json.load(sys.stdin)
    if not data:
        die("baseline_interpreter_table", "no variants in analyzed input")

    columns = [{"key": "metric", "label": "Metric", "align": "left", "format": "str"}]
    for key in COLUMN_ORDER:
        columns.append({"key": key, "label": COLUMN_LABELS[key],
                        "align": "right", "format": "str"})

    corpus_row = ["Corpus size"] + ["1"] * len(COLUMN_ORDER)

    loaded_row = ["Processes loaded"]
    for key in COLUMN_ORDER:
        if key not in data:
            loaded_row.append("--")
            continue
        loaded_row.append(fmt_scalar(
            dig(data[key], "n_procs", key, "baseline_interpreter_table")["mean"],
            "count",
        ))

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps(
        {"columns": columns, "rows": [corpus_row, loaded_row]}, indent=2
    ) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
