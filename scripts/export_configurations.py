#!/usr/bin/env python3
"""Emit paper/lib/json/configurations.json from fossils/configurations.toml.

Also validates that every variant slug declared in EXEC_CONFIG_FOSSILS'
fossil.toml [variants] block is declared in the registry. Other fossils use
workload names or A/B axis labels as variant slugs and are not checked.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "fossils" / "configurations.toml"
OUTPUT = ROOT / "paper" / "lib" / "json" / "configurations.json"
FOSSILS_DIR = ROOT / "fossils"

# Fossils whose [variants] slugs are execution configurations (must match
# the registry). Other fossils use workload names, A/B axes, or per-benchmark
# labels for their variants and are exempt from the check.
EXEC_CONFIG_FOSSILS = (
    "7-2-restricted-execution",
    "7-5-cross-process-memory-sharing",
)


def load_registry() -> dict:
    with REGISTRY.open("rb") as f:
        return tomllib.load(f)


def collect_exec_config_slugs() -> set[str]:
    slugs = set()
    for name in EXEC_CONFIG_FOSSILS:
        fossil_toml = FOSSILS_DIR / name / "fossil.toml"
        if not fossil_toml.exists():
            continue
        with fossil_toml.open("rb") as f:
            cfg = tomllib.load(f)
        slugs.update(cfg.get("variants", {}).keys())
    return slugs


def main() -> int:
    registry = load_registry()
    declared = set(registry.keys())
    used = collect_exec_config_slugs()

    undeclared = used - declared
    if undeclared:
        print(
            f"error: variant slugs used in EXEC_CONFIG_FOSSILS but missing "
            f"from {REGISTRY.name}: {sorted(undeclared)}",
            file=sys.stderr,
        )
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(registry, indent=2, sort_keys=False) + "\n")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")

    unused = declared - used
    if unused:
        print(
            f"note: registry entries not referenced by any exec-config "
            f"fossil variant: {sorted(unused)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
