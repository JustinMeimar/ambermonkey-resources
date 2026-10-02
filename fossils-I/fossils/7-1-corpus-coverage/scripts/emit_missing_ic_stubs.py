#!/usr/bin/env python3
"""List the CacheIR stub bodies missing from the AOT corpus, per workload.

Reads records/ directly rather than the fossil analyze pipeline because the
per-body payload is a list of dicts (cache_kind, ir_hex, ...) that io.py's
Metric parser flattens away.  The reducer's summary already contains the
dedup'd bodies under `missing_ic_stub_bodies`; we just aggregate across the
latest run of each variant and emit a typst-compatible table + headline
scalars for the paper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "figures"))


import glob
import json
import os

from figure_data import table_json

FOSSIL_DIR = Path(__file__).resolve().parents[1]
RECORDS_DIR = FOSSIL_DIR / "records"
VARIANTS = ("tp6_test", "speedometer3", "jetstream3", "octane2")

# CacheKind enum ordering mirrors the CACHE_IR_KINDS(_) macro in
# js/src/jit/CacheIR.h. Keep in sync when SpiderMonkey adds new kinds.
CACHE_KIND_NAMES = [
    "GetProp", "GetElem", "GetName", "GetPropSuper", "GetElemSuper",
    "GetImport", "LazyConstant", "SetProp", "SetElem", "BindName",
    "In", "HasOwn", "CheckPrivateField", "TypeOf", "TypeOfEq",
    "ToPropertyKey", "InstanceOf", "GetIterator", "CloseIter",
    "OptimizeGetIterator", "OptimizeSpreadCall", "Compare", "ToBool",
    "Call", "UnaryArith", "BinaryArith", "NewObject", "NewArray",
    "Lambda",
]


def kind_name(idx):
    return CACHE_KIND_NAMES[idx] if 0 <= idx < len(CACHE_KIND_NAMES) else f"Kind{idx}"


def latest_record(variant):
    matches = sorted(
        p for p in RECORDS_DIR.iterdir()
        if p.is_dir() and f"_{variant}_" in p.name
    )
    return matches[-1] if matches else None


def summary_for(record_dir):
    results = json.loads((record_dir / "results.json").read_text())
    for obs in results.get("observations", []):
        stdout = obs.get("stdout")
        if isinstance(stdout, list):
            stdout = "\n".join(stdout)
        if not stdout:
            continue
        # Reducer writes one JSON blob per iteration; take the last line.
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit("emit_missing_ic_stubs: usage: emit_missing_ic_stubs.py <out.json>")

    per_variant = {}
    for variant in VARIANTS:
        record = latest_record(variant)
        if record is None:
            continue
        summary = summary_for(record)
        if summary is None:
            continue
        per_variant[variant] = {
            "record": record.name,
            "bodies": summary.get("missing_ic_stub_bodies", []) or [],
            "shape_count": int(summary.get("missing_ic_shape_count", 0)),
            "body_count": int(summary.get("missing_ic_body_count", 0)),
            "attach_total": int(summary.get("missing_ic_attach_total", 0)),
        }

    columns = [
        {"key": "workload",     "label": "Workload",      "align": "left",  "format": "str"},
        {"key": "kind",         "label": "Kind",          "align": "left",  "format": "str"},
        {"key": "attach_count", "label": "Attaches",      "align": "right", "format": "int"},
        {"key": "shape_count",  "label": "Shapes",        "align": "right", "format": "int"},
        {"key": "ir_bytes",     "label": "IR bytes",      "align": "right", "format": "int"},
        {"key": "ir_hex",       "label": "CacheIR (hex)", "align": "left",  "format": "str"},
    ]
    rows = []
    for variant in VARIANTS:
        entry = per_variant.get(variant)
        if not entry:
            continue
        for body in entry["bodies"]:
            rows.append([
                variant,
                kind_name(body.get("cache_kind", -1)),
                body.get("attach_count", 0),
                body.get("shape_count", 0),
                body.get("ir_bytes", len(body.get("ir_hex", "")) // 2),
                body.get("ir_hex", ""),
            ])

    out_path = Path(sys.argv[1]) / "missing-ic-stubs.json"
    out_path.write_text(table_json(columns=columns, rows=rows))

    payload = json.loads(out_path.read_text())
    payload["variants_present"] = list(per_variant.keys())
    for variant, entry in per_variant.items():
        payload[f"{variant}_missing_ic_body_count"] = entry["body_count"]
        payload[f"{variant}_missing_ic_shape_count"] = entry["shape_count"]
        payload[f"{variant}_missing_ic_attach_total"] = entry["attach_total"]
        payload[f"{variant}_source_record"] = entry["record"]
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
