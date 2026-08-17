"""Manifest + command-line inspection helpers.

Every fossil analysis script needs to load the manifest for the current
observation and interrogate the burial command to confirm the variant was
run with the settings it claims. These helpers centralise the patterns
that were previously copy-pasted across parse_speedometer.py /
parse_overhead.py / parse_performance.py.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def fail(prefix: str, msg: str) -> "NoReturn":
    print(f"{prefix}: {msg}", file=sys.stderr)
    raise SystemExit(1)


def load(prefix: str = "manifest") -> dict:
    """Read manifest.json from $FOSSIL_RUN_DIR."""
    run_dir = os.environ.get("FOSSIL_RUN_DIR")
    if not run_dir:
        fail(prefix, "FOSSIL_RUN_DIR is required")
    path = Path(run_dir) / "manifest.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(prefix, f"cannot read {path}: {exc}")


def command_flag(command: str, name: str) -> bool:
    """True if ``NAME=true`` appears as a whitespace-delimited token."""
    pattern = rf"(?:^|\s){re.escape(name)}=true(?=\s|$)"
    return re.search(pattern, command) is not None


def has_option(command: str, option: str, value: str) -> bool:
    """True if ``--option value`` or ``--option=value`` appears."""
    pattern = rf"{re.escape(option)}(?:=|\s+){re.escape(value)}(?:\s|$)"
    return re.search(pattern, command) is not None


def page_cycles_from(command: str, prefix: str = "manifest") -> int:
    """Extract the ``--page-cycles`` integer (must appear exactly once)."""
    matches = re.findall(
        r"(?:^|\s)--page-cycles(?:=|\s+)(\d+)(?=\s|$)", command
    )
    if len(matches) != 1:
        fail(prefix, "command must contain exactly one --page-cycles value")
    page_cycles = int(matches[0])
    if page_cycles < 1:
        fail(prefix, "--page-cycles must be positive")
    return page_cycles
