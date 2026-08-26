#!/usr/bin/env python3
"""Reduce demand records used by the frozen tp6 train/test split.

The fossil retains records for retired variants from earlier versions of the
experiment. Fossil analyzes the latest record for every historical variant,
so return an empty metric for those variants and apply the strict reducer only
to the 32 workloads used by the cumulative-coverage figure.
"""

import os
import subprocess
import sys
from pathlib import Path

FOSSIL_DIR = Path(__file__).resolve().parent.parent
SPLIT_DIR = FOSSIL_DIR.parent / "6-1-corpus-construction"
STRICT_REDUCER = Path(__file__).with_name("ic_set.py")


def read_sites(path):
    return {
        line.split("#", 1)[0].strip()
        for line in path.read_text().splitlines()
        if line.split("#", 1)[0].strip()
    }


variant = os.environ.get("FOSSIL_VARIANT_NAME", "")
sites = read_sites(SPLIT_DIR / "train.txt") | read_sites(SPLIT_DIR / "test.txt")
observation = sys.stdin.buffer.read()
if variant not in sites:
    print("{}")
    sys.exit(0)

result = subprocess.run(
    [str(STRICT_REDUCER)],
    input=observation,
    stdout=sys.stdout.buffer,
    stderr=sys.stderr.buffer,
    check=False,
)
sys.exit(result.returncode)
