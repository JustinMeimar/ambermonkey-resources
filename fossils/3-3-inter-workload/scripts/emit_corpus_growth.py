#!/usr/bin/env python3
"""Emit the tp6-Train prefix coverage curve against the tp6-Test oracle."""

import json
import sys

from corpus_growth import (
    ALPHABETICAL_TRAIN_ORDER,
    coverage_curve,
)
from pairwise import load_counters, split_sites


def main():
    train_sites, test_sites = split_sites()
    train_sites = tuple(sorted(train_sites))
    all_sites = train_sites + test_sites
    _, ic_sets, ic_freqs, bl_sets, bl_freqs = load_counters(sites=all_sites)
    output = coverage_curve(
        train_sites,
        test_sites,
        ic_sets,
        ic_freqs,
        bl_sets,
        bl_freqs,
        order_policy=ALPHABETICAL_TRAIN_ORDER,
    )

    destination = sys.argv[1] if len(sys.argv) > 1 else None
    if destination:
        with open(destination, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
