"""Raptor stdout → suite dict.

Raptor writes its JSON to stdout, but fossil captures stdout as either a
string or a list of lines depending on the runner. This module normalises
the shape and returns the ``suites[0]`` dict callers actually work with.
"""

from __future__ import annotations

import json

from . import manifest


def load(observation: dict, prefix: str = "raptor") -> dict:
    """Parse a raptor JSON blob from an observation's stdout."""
    stdout = observation.get("stdout", "")
    text = "\n".join(stdout) if isinstance(stdout, list) else stdout
    if not isinstance(text, str) or not text.strip():
        manifest.fail(prefix, "empty stdout; raptor produced no JSON")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        manifest.fail(prefix, f"malformed raptor JSON: {exc}")


def single_suite(raptor: dict, expected_name: str, prefix: str = "raptor") -> dict:
    """Return the single suite from a raptor result, verifying its name."""
    suites = raptor.get("suites") or []
    if len(suites) != 1:
        manifest.fail(
            prefix,
            f"expected exactly one raptor suite, found {len(suites)}",
        )
    suite = suites[0]
    if suite.get("name") != expected_name:
        manifest.fail(
            prefix,
            f"expected {expected_name!r} suite, found {suite.get('name')!r}",
        )
    return suite
