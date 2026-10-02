#!/usr/bin/env python3
"""Re-emit the reducer's trailing JSON blob so fossil sees each leaf as a Scalar."""

import json
import sys


def die(msg):
    print(f"parse_coverage: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    obs = json.load(sys.stdin)
    stdout = obs.get("stdout", "")
    if isinstance(stdout, list):
        stdout = "\n".join(stdout)

    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        die("empty stdout; reducer did not run")

    try:
        summary = json.loads(lines[-1])
    except json.JSONDecodeError as e:
        die(f"reducer output was not JSON: {e}\nlast line: {lines[-1][:200]}")

    json.dump(summary, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
