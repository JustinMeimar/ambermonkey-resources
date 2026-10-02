#!/usr/bin/env python3
"""Render the top content-process guest IC bodies by stub-entry count."""

import collections
import json
import sys


TOP_N = 20
ID_PREFIX = 10


def die(message):
    print(f"ic_top_table: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def main():
    document = json.load(sys.stdin)
    attaches = collections.Counter()
    entered = collections.Counter()
    for observation in document.get("observations", [document]):
        output = observation.get("stdout")
        if isinstance(output, list):
            output = "\n".join(output)
        if not isinstance(output, str) or not output.strip():
            die("observation has no reducer output on stdout")
        reduced = json.loads(output.strip())
        content = reduced.get("ic", {}).get("content", {})
        attaches.update(content.get("attaches", {}))
        entered.update(content.get("entered", {}))

    if not attaches:
        die("no guest content-process IC attachments")
    unattached = set(entered) - set(attaches)
    if unattached:
        die("stub-entry counts contain bodies absent from the static inventory")
    total = sum(entered.values())
    if total == 0:
        die("guest IC inventory has zero observed stub entries")

    rows = []
    cdf = 0.0
    for body_id, count in entered.most_common(TOP_N):
        share = count / total
        cdf += share
        rows.append([body_id[:ID_PREFIX], count, share, cdf])

    table = {
        "columns": [
            {"key": "body", "label": "IC body", "align": "left", "format": "str"},
            {"key": "entries", "label": "Entries", "align": "right", "format": "int"},
            {"key": "share", "label": "Share", "align": "right", "format": "percent"},
            {"key": "cdf", "label": "CDF", "align": "right", "format": "percent"},
        ],
        "rows": rows,
    }
    json.dump(table, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
