#!/usr/bin/env python3
"""Rank the static guest IC inventory by content-process stub entries."""

import collections
import json
import math
import sys


TOP_FRACTION = 0.10
COVERAGE_FRACTION = 0.90


def die(message):
    print(f"ic_rank: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def reduced_observations(document):
    for observation in document.get("observations", [document]):
        output = observation.get("stdout")
        if isinstance(output, list):
            output = "\n".join(output)
        if not isinstance(output, str) or not output.strip():
            die("observation has no reducer output on stdout")
        try:
            yield json.loads(output.strip())
        except json.JSONDecodeError as exc:
            die(f"invalid reducer JSON: {exc}")


def main():
    document = json.load(sys.stdin)
    attaches = collections.Counter()
    entered = collections.Counter()
    for reduced in reduced_observations(document):
        content = reduced.get("ic", {}).get("content", {})
        attaches.update(content.get("attaches", {}))
        entered.update(content.get("entered", {}))

    if not attaches:
        die("no guest content-process IC attachments")
    unattached = set(entered) - set(attaches)
    if unattached:
        sample = ", ".join(sorted(unattached)[:3])
        die(f"entered bodies lack a corresponding attachment: {sample}")

    # Attachment keys are the static inventory. Keep zero-entry bodies in the
    # sequence so x positions and percentages are relative to that inventory.
    ranked = sorted((entered.get(body, 0) for body in attaches), reverse=True)
    total = sum(ranked)
    if total == 0:
        die("guest IC inventory has zero observed stub entries")

    top_10_count = max(1, math.ceil(len(ranked) * TOP_FRACTION))
    top_10_share = sum(ranked[:top_10_count]) / total
    cumulative = 0
    bodies_90 = 0
    for bodies_90, count in enumerate(ranked, 1):
        cumulative += count
        if cumulative / total >= COVERAGE_FRACTION:
            break

    result = {
        "ranked_counts": ranked,
        "static_body_count": len(ranked),
        "entered_body_count": sum(count > 0 for count in ranked),
        "total_stub_entries": total,
        "top_10_body_count": top_10_count,
        "top_10_share": top_10_share,
        "bodies_90": bodies_90,
        "bodies_90_share_of_inventory": bodies_90 / len(ranked),
        "top_fraction": TOP_FRACTION,
        "coverage_fraction": COVERAGE_FRACTION,
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
