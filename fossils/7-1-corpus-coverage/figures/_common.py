"""Shared helpers for the coverage figure scripts."""

import json
import pathlib
import sys


COLUMN_ORDER = ("tp6_test", "speedometer3", "jetstream3")

COLUMN_LABELS = {
    "tp6_test":     "tp6-Test",
    "speedometer3": "Speedometer 3.1",
    "jetstream3":   "JetStream 3.0",
}


def die(name, msg):
    sys.exit(f"{name}: {msg}")


def dig(node, path, variant, name):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            die(name, f"{variant}: no {path!r}; record predates the request-time schema")
        node = node[part]
    return node


def fmt_scalar(mean, kind):
    if kind == "percent":
        return f"{mean:.1f}%"
    if abs(mean) >= 1_000_000:
        return f"{mean/1e6:.2f}M"
    if abs(mean) >= 10_000:
        return f"{mean/1e3:.1f}k"
    return f"{mean:,.0f}"


def _load_and_check(name):
    data = json.load(sys.stdin)
    if not data:
        die(name, "no variants in analyzed input")
    return data


def emit_aggregate(name, rows_spec):
    """Three-column table: tp6-Test, Speedometer 3.1, JetStream 3.0.

    Each column pulls the per-iteration mean of the same reducer path
    from its named variant. rows_spec is a list of
    (label, dotted_path, kind) tuples matching the reducer's summary
    schema (see reduce_coverage.py). Reads the cross-variant fold on
    stdin and writes a JSON table to sys.argv[1]'s .json sibling."""
    data = _load_and_check(name)

    columns = [{"key": "metric", "label": "Metric", "align": "left", "format": "str"}]
    for key in COLUMN_ORDER:
        columns.append({"key": key, "label": COLUMN_LABELS[key],
                        "align": "right", "format": "str"})

    rows = []
    for label, path, kind in rows_spec:
        row = [label]
        for key in COLUMN_ORDER:
            if key not in data:
                row.append("--")
                continue
            scalar = dig(data[key], path, key, name)
            row.append(fmt_scalar(scalar["mean"], kind))
        rows.append(row)

    out = pathlib.Path(sys.argv[1]).with_suffix(".json")
    out.write_text(json.dumps({"columns": columns, "rows": rows}, indent=2) + "\n")
    print(f"wrote {out}")
