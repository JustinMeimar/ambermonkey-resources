#!/usr/bin/env python3

from collections import OrderedDict
import json
import sys


def replay(installs, capacity):
    entries = OrderedDict()
    used = 0
    hits = 0
    for item in installs:
        key = tuple(item["cache_key"])
        size = item["cache_bytes"]
        if key in entries:
            hits += 1
            entries.move_to_end(key)
            continue
        if size > capacity:
            continue
        while used + size > capacity:
            _, evicted = entries.popitem(last=False)
            used -= evicted
        entries[key] = size
        used += size
    return hits


def main():
    observation = json.load(sys.stdin)
    records = [json.loads(line) for line in observation["stdout"]]
    summaries = [item for item in records if item["event"] == "summary"]
    if len(summaries) != 1 or summaries[0]["raptor_exit_code"] != 0:
        raise SystemExit("Raptor did not complete successfully")
    if summaries[0]["install"] == 0:
        raise SystemExit("no Baseline installations recorded")
    installs = sorted(
        (item for item in records if item["event"] == "install"
         and item["provenance"] == "guest" and item["key_has_source"]),
        key=lambda item: item["timestamp_us"],
    )
    keys = {tuple(item["cache_key"]) for item in installs}
    sizes = {}
    for item in installs:
        key = tuple(item["cache_key"])
        sizes.setdefault(key, set()).add(
            (item["code_bytes"], item["allocated_code_bytes"], item["metadata_bytes"])
        )
    result = {
        "guest_installs": len(installs),
        "candidate_keys": len(keys),
        "candidate_repeat_installs": len(installs) - len(keys),
        "variable_size_keys": sum(len(values) > 1 for values in sizes.values()),
        "malformed_lines": summaries[0]["malformed"],
        "processes": len({item["pid"] for item in installs}),
        "candidate_lru_hits": {f"{mib}mib": replay(installs, mib * 1024 * 1024)
                               for mib in (4, 8, 16)},
    }
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
