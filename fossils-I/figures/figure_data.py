from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True, slots=True)
class Scalar:
    mean: float
    stddev: float


@dataclass(frozen=True, slots=True)
class Metric:
    scalar: Scalar | None = None
    children: dict[str, Metric] | None = None
    sequence: list[Scalar] | None = None
    tag: str | None = None

    def walk_scalars(self, prefix: str = "") -> list[tuple[str, Scalar]]:
        results: list[tuple[str, Scalar]] = []
        if self.scalar is not None:
            results.append((prefix, self.scalar))
        if self.children is not None:
            for key, child in self.children.items():
                path = f"{prefix}.{key}" if prefix else key
                results.extend(child.walk_scalars(path))
        return results


@dataclass(frozen=True, slots=True)
class FigureData:
    columns: dict[str, Metric]

    @property
    def column_names(self) -> list[str]:
        return list(self.columns.keys())

    def flat_table(self) -> dict[str, dict[str, Scalar]]:
        table: dict[str, dict[str, Scalar]] = {}
        for col, metric in self.columns.items():
            table[col] = dict(metric.walk_scalars())
        return table


def _parse_scalar(raw: dict) -> Scalar:
    return Scalar(mean=raw["mean"], stddev=raw["stddev"])


def _parse_metric(raw: object) -> Metric:
    if isinstance(raw, dict):
        if "mean" in raw and "stddev" in raw and len(raw) == 2:
            return Metric(scalar=_parse_scalar(raw))
        children = {k: _parse_metric(v) for k, v in raw.items()}
        return Metric(children=children)
    if isinstance(raw, list):
        items = []
        for item in raw:
            if isinstance(item, dict) and "mean" in item and "stddev" in item:
                items.append(_parse_scalar(item))
            elif isinstance(item, (int, float)):
                items.append(Scalar(mean=float(item), stddev=0.0))
            else:
                return Metric()
        return Metric(sequence=items)
    if isinstance(raw, (int, float)):
        return Metric(scalar=Scalar(mean=float(raw), stddev=0.0))
    if isinstance(raw, str):
        return Metric(tag=raw)
    return Metric()


def parse_data(raw: dict) -> FigureData:
    columns = {name: _parse_metric(value) for name, value in raw.items()}
    return FigureData(columns=columns)


_ALLOWED_FORMATS = {"str", "int", "float", "percent"}
_ALLOWED_ALIGNS = {"left", "right", "center"}


def table_json(
    columns: Sequence[dict[str, Any]],
    rows: Iterable[Sequence[Any]],
) -> str:
    """Format the column-and-row JSON consumed by the paper tables."""
    cols: list[dict[str, Any]] = []
    for i, col in enumerate(columns):
        if "key" not in col or "label" not in col:
            raise ValueError(f"column {i} missing 'key' or 'label'")
        fmt = col.get("format", "str")
        if fmt not in _ALLOWED_FORMATS:
            raise ValueError(
                f"column {col['key']}: format {fmt!r} not in {sorted(_ALLOWED_FORMATS)}"
            )
        align = col.get("align", "left")
        if align not in _ALLOWED_ALIGNS:
            raise ValueError(
                f"column {col['key']}: align {align!r} not in {sorted(_ALLOWED_ALIGNS)}"
            )
        cols.append(
            {"key": col["key"], "label": col["label"], "format": fmt, "align": align}
        )

    materialised = [list(r) for r in rows]
    for r_idx, row in enumerate(materialised):
        if len(row) != len(cols):
            raise ValueError(
                f"row {r_idx} has {len(row)} cells, expected {len(cols)}"
            )

    payload: dict[str, Any] = {"columns": cols, "rows": materialised}
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"
