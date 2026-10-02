#!/usr/bin/env python3

import json
from pathlib import Path
import sys

from analyze_detail import analyze_record


def main():
    workload = analyze_record(Path(sys.argv[2]), json.load(sys.stdin))
    candidate = workload["candidate"]
    json.dump({
        "guest_installs": candidate["installs"],
        "candidate_keys": candidate["keys"],
        "candidate_repeat_installs": candidate["installs"] - candidate["keys"],
        "recurrence_scope": candidate["recurrence_scope"],
        "variable_size_keys": candidate["variable_size_keys"],
        "malformed_lines": workload["recording"]["malformed"],
    }, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
