#!/usr/bin/env python3
"""Aggregate per-pid AOT coverage dumps from one iteration into a single JSON summary."""

import glob
import json
import os
import sys


def die(msg):
    print(f"reduce_coverage: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def main(root):
    files = sorted(glob.glob(os.path.join(root, "cov.*")))
    if not files:
        die(f"no coverage dumps under {root} - did AOTCoverage arm? "
            "check that JS_AOT_COVERAGE_OUT and JIT_OPTION_useAOTImage "
            "reached the firefox children via raptor --setenv")

    bl_total = 0
    ic_total = 0
    bl_installs = {}
    bl_self_hosted = set()
    ic_attaches = {}
    shapes_aot = set()
    shapes_other = set()
    req = {
        "bl_aot": 0, "bl_compiled": 0,
        "ic_aot": 0, "ic_zone": 0, "ic_compiled": 0,
    }

    for path in files:
        with open(path) as f:
            d = json.load(f)

        corpus = d.get("corpus", {})
        if bl_total == 0:
            bl_total = int(corpus.get("baseline_functions", 0))
            ic_total = int(corpus.get("ic_stubs", 0))

        r = d.get("requests", {})
        rb = r.get("baseline_functions", {})
        ri = r.get("ic_stubs", {})
        req["bl_aot"] += int(rb.get("aot_hit", 0))
        req["bl_compiled"] += int(rb.get("compiled", 0))
        req["ic_aot"] += int(ri.get("aot_hit", 0))
        req["ic_zone"] += int(ri.get("zone_cache_hit", 0))
        req["ic_compiled"] += int(ri.get("compiled", 0))

        for e in d.get("baseline_functions", []) or []:
            blob = e["blob"]
            bl_installs[blob] = bl_installs.get(blob, 0) + int(e.get("installs", 0))
            if e.get("self_hosted"):
                bl_self_hosted.add(blob)
        for e in d.get("ic_stubs", []) or []:
            blob = e["blob"]
            ic_attaches[blob] = ic_attaches.get(blob, 0) + int(e.get("attaches", 0))

        shapes_aot.update(d.get("ic_shapes_aot", []) or [])
        shapes_other.update(d.get("ic_shapes_other", []) or [])

    # A corpus shape normally always resolves out of the image, so the sets
    # are near-disjoint. They can overlap for requests that land before the
    # image finishes loading into the atoms zone. Served-anywhere wins, and
    # the overlap is reported so a large one is visible rather than silent.
    overlap = shapes_aot & shapes_other
    shapes_other -= overlap

    bl_used = sum(1 for n in bl_installs.values() if n > 0)
    ic_used = sum(1 for n in ic_attaches.values() if n > 0)
    sh_used = sum(1 for b in bl_self_hosted if bl_installs.get(b, 0) > 0)

    bl_req_total = req["bl_aot"] + req["bl_compiled"]
    ic_req_total = req["ic_aot"] + req["ic_zone"] + req["ic_compiled"]
    shapes_requested = len(shapes_aot) + len(shapes_other)

    out = {
        "utilization": {
            "baseline_functions": {
                "used": bl_used, "total": bl_total,
                "pct": pct(bl_used, bl_total),
            },
            "ic_stubs": {
                "used": ic_used, "total": ic_total,
                "pct": pct(ic_used, ic_total),
            },
        },
        "requests": {
            "baseline_functions": {
                "aot_hit": req["bl_aot"],
                "compiled": req["bl_compiled"],
                "total": bl_req_total,
                "aot_hit_pct": pct(req["bl_aot"], bl_req_total),
            },
            "ic_stubs": {
                "aot_hit": req["ic_aot"],
                "zone_cache_hit": req["ic_zone"],
                "compiled": req["ic_compiled"],
                "total": ic_req_total,
                "aot_hit_pct": pct(req["ic_aot"], ic_req_total),
            },
        },
        "workload": {
            "ic_shapes_requested": shapes_requested,
            "ic_shapes_served": len(shapes_aot),
            "ic_shapes_raced": len(overlap),
            "coverage_pct": pct(len(shapes_aot), shapes_requested),
        },
        "self_hosted_used_baseline": sh_used,
        "n_procs": len(files),
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        die("usage: reduce_coverage.py <coverage-dir>")
    main(sys.argv[1])
