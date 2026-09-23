#!/usr/bin/env python3
"""Pool content-process Baseline and IC demand across repetitions."""

import collections
import json
import sys


def die(message):
    print(f"artifact-sets: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def observation_output(observation):
    if int(observation.get("exit_code", 1)) != 0:
        die(
            f"iteration {observation.get('iteration', '?')} exited with "
            f"status {observation.get('exit_code')}"
        )

    output = observation.get("stdout")
    if isinstance(output, list):
        output = "\n".join(output)
    if not isinstance(output, str) or not output.strip():
        die(f"iteration {observation.get('iteration', '?')} has no JSON output")

    try:
        return json.loads(output.strip())
    except json.JSONDecodeError as error:
        die(f"iteration {observation.get('iteration', '?')} emitted invalid JSON: {error}")


def counter_at(payload, kind, metric):
    values = (((payload.get(kind) or {}).get("content") or {}).get(metric) or {})
    try:
        return collections.Counter({key: int(value) for key, value in values.items()})
    except (TypeError, ValueError) as error:
        die(f"invalid {kind}.content.{metric} counter: {error}")


def encode_set(values):
    return ",".join(sorted(values))


def encode_counter(values):
    return ";".join(
        f"{key}={value}"
        for key, value in sorted(values.items(), key=lambda item: (-item[1], item[0]))
    )


def main():
    record = json.load(sys.stdin)
    observations = record.get("observations") or [record]

    ic_requests = collections.Counter()
    ic_entries = collections.Counter()
    baseline_compiles = collections.Counter()
    baseline_entries = collections.Counter()

    for observation in observations:
        payload = observation_output(observation)
        ic_requests.update(counter_at(payload, "ic", "attaches"))
        ic_entries.update(counter_at(payload, "ic", "entered"))
        baseline_compiles.update(counter_at(payload, "baseline", "compiles"))
        baseline_entries.update(counter_at(payload, "baseline", "entered"))

    if not ic_requests:
        die("no content-process IC attachment identities")
    if not ic_entries:
        die("no content-process IC entry counts")
    if not baseline_compiles:
        die("no content-process Baseline compilation identities")
    if not baseline_entries:
        die("no content-process Baseline entry counts")

    missing_ic_bodies = set(ic_entries) - set(ic_requests)
    if missing_ic_bodies:
        die(
            f"{len(missing_ic_bodies)} entered IC bodies have no corresponding "
            "attachment event"
        )

    missing_baseline_functions = set(baseline_entries) - set(baseline_compiles)
    if missing_baseline_functions:
        die(
            f"{len(missing_baseline_functions)} entered Baseline functions "
            "have no corresponding compilation event"
        )

    json.dump(
        {
            "ic_hashes": encode_set(ic_requests),
            "ic_freqs": encode_counter(ic_entries),
            "baseline_hashes": encode_set(baseline_compiles),
            "baseline_freqs": encode_counter(baseline_entries),
            "baseline_compile_freqs": encode_counter(baseline_compiles),
            "ic_count": len(ic_requests),
            "ic_entries": sum(ic_entries.values()),
            "baseline_count": len(baseline_compiles),
            "baseline_compiles": sum(baseline_compiles.values()),
            "baseline_entries": sum(baseline_entries.values()),
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
