"""Speedometer 3 suite → normalised metrics.

Canonical shape:

    {
        "score": float,          # suite score, higher is better
        "total_ms": float,       # total wall time in ms
        "workloads_ms": {name: ms},  # per-workload /total values in ms
    }

The 20-workload count is a hard invariant; a partial run indicates a
browser or harness failure and should abort the analysis.
"""

from __future__ import annotations

from . import manifest, raptor

SUITE_NAME = "speedometer3"
EXPECTED_WORKLOADS = 20


def _positive(value, name: str, prefix: str) -> float:
    if not isinstance(value, (int, float)) or value <= 0:
        manifest.fail(prefix, f"{name} must be a positive number, got {value!r}")
    return float(value)


def parse(suite: dict, prefix: str = "speedometer3") -> dict:
    """Reduce one speedometer3 suite dict to canonical metrics."""
    try:
        lookup = {sub["name"]: sub for sub in suite["subtests"]}
    except (KeyError, TypeError) as exc:
        manifest.fail(prefix, f"malformed subtests: {exc}")

    workloads_ms = {
        name.removesuffix("/total"): _positive(
            lookup[name].get("value"), name, prefix
        )
        for name in sorted(lookup)
        if name.endswith("/total")
    }
    if len(workloads_ms) != EXPECTED_WORKLOADS:
        manifest.fail(
            prefix,
            f"expected {EXPECTED_WORKLOADS} workload totals, got {len(workloads_ms)}",
        )

    return {
        "score": _positive(lookup.get("score", {}).get("value"), "score", prefix),
        "total_ms": _positive(lookup.get("total", {}).get("value"), "total", prefix),
        "workloads_ms": workloads_ms,
    }


def parse_observation(observation: dict, prefix: str = "speedometer3") -> dict:
    """Convenience: raptor.load + raptor.single_suite + parse."""
    r = raptor.load(observation, prefix)
    suite = raptor.single_suite(r, SUITE_NAME, prefix)
    return parse(suite, prefix)
