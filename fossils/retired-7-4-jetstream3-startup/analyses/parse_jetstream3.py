#!/usr/bin/env python3
"""Reduce a raptor JS3 JSON result to overall/startup score metrics."""

import json
import os
import sys

sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
from benchmarks import raptor, jetstream3

PREFIX = "parse_jetstream3"


def main():
    obs = json.load(sys.stdin)
    r = raptor.load(obs, PREFIX)
    suite = raptor.single_suite(r, jetstream3.SUITE_NAME, PREFIX)
    overall = jetstream3.parse_overall(suite, PREFIX)
    startup = jetstream3.parse_startup(suite, PREFIX)

    json.dump({
        "overall_score": overall,
        "startup_score": startup["startup_score"],
        "startup_geomean_ms": startup["startup_geomean_ms"],
        "n_subtests": startup["n_subtests"],
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
