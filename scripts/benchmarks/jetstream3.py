"""JetStream 3 suite → normalised metrics.

JetStream 3 emits per-subtest scores in several flavours (First, Worst,
Average, Geometric, MainRun, Stdlib). Different fossils care about different
reductions, so this module exposes the primitives rather than forcing one
shape:

    parse_overall(suite)     -> suite.value (with replicates[0] fallback)
    parse_geometric(suite)   -> {name: geomean_score} per base benchmark
    parse_startup(suite)     -> {startup_geomean_ms, startup_score, n_subtests}

Higher-is-better throughout: JetStream 3 subtest values are scores.
"""

from __future__ import annotations

import math

from . import manifest, raptor

SUITE_NAME = "jetstream3"

# Non-benchmark subtests to drop from per-benchmark reductions.
_EXCLUDE_BASES = frozenset({"score", "cpuTime"})


def parse_overall(suite: dict, prefix: str = "jetstream3") -> float:
    """Return the suite-level score, falling back to replicates[0]."""
    overall = suite.get("value")
    if isinstance(overall, (int, float)):
        return float(overall)
    reps = suite.get("replicates") or []
    if reps and isinstance(reps[0], (int, float)):
        return float(reps[0])
    manifest.fail(prefix, "no suite-level score in raptor JSON")


def parse_geometric(suite: dict, prefix: str = "jetstream3") -> dict:
    """Return ``{base_bench: score}`` from each ``<base>-Geometric`` subtest.

    Geometric is JetStream 3's canonical per-benchmark score. Housekeeping
    subtests (score, cpuTime) are excluded even if a Geometric variant is
    reported so downstream figures only bar-plot real benchmarks.
    """
    out: dict[str, float] = {}
    for entry in suite.get("subtests") or []:
        name = entry.get("name", "")
        if not name.endswith("-Geometric"):
            continue
        value = entry.get("value")
        if not isinstance(value, (int, float)) or value <= 0:
            continue
        base = name.removesuffix("-Geometric")
        if base in _EXCLUDE_BASES:
            continue
        out[base] = float(value)
    if not out:
        manifest.fail(prefix, "no positive -Geometric subtests")
    return out


def parse_startup(suite: dict, prefix: str = "jetstream3") -> dict:
    """Geomean of ``<name>-First`` subtest values, expressed two ways.

    startup_geomean_ms is the raw geomean in ms (lower is better).
    startup_score = 1000 / startup_geomean_ms so it composes with
    overall score on a higher-is-better axis.
    """
    subtests = suite.get("subtests") or []
    firsts = [
        s["value"] for s in subtests
        if s.get("name", "").endswith("-First")
        and isinstance(s.get("value"), (int, float))
        and s["value"] > 0
    ]
    if not firsts:
        manifest.fail(prefix, "no positive -First subtest values")
    startup_geomean_ms = math.exp(sum(math.log(v) for v in firsts) / len(firsts))
    return {
        "startup_geomean_ms": startup_geomean_ms,
        "startup_score": 1000.0 / startup_geomean_ms,
        "n_subtests": len(firsts),
    }


def parse_observation(observation: dict, prefix: str = "jetstream3") -> dict:
    """Convenience: raptor.load + raptor.single_suite + parse to canonical shape."""
    r = raptor.load(observation, prefix)
    suite = raptor.single_suite(r, SUITE_NAME, prefix)
    return {
        "score": parse_overall(suite, prefix),
        "subtests_score": parse_geometric(suite, prefix),
    }
