#!/usr/bin/env python3

import json
from pathlib import Path
import sys

from analyze_detail import analyze_record
from render_dashboard import render


def main():
    output_dir = Path(sys.argv[1])
    destination = output_dir / "detail.json"
    fossil = Path(__file__).resolve().parent
    records = sorted((p for p in (fossil / "records").iterdir()
                      if (p / "manifest.json").is_file() and (p / "results.json").is_file()))
    latest = {}
    for path in records:
        manifest = json.loads((path / "manifest.json").read_text())
        latest[manifest["variant"]] = path
    if not latest:
        raise SystemExit("no browser recordings found")
    with destination.open("w") as output:
        output.write('{"schema_version":1,"methodology":')
        json.dump({
            "candidate": "guest Baseline installs with a source fingerprint",
            "key": "filename, source span and encoding, source and bytecode hashes, immutable flags, debug instrumentation",
            "recurrence": "same exact key in chronological order within one browser recording",
            "scope": "classification uses the most recent earlier install of the same key",
            "cache": "global byte-capacity LRU across all recorded processes; capacity limits retained lookup entries, not total live browser code memory; sizes are direct recorded allocations, not RSS",
            "size_models": "instructions = emitted machine instructions only; allocated_code = JitCode executable buffer plus header; code_plus_metadata = allocated_code plus BaselineScript allocation; size_split treats different recorded size tuples for one candidate key as distinct entries",
            "recurrence_gap": "elapsed wall-clock time since the preceding install with the same candidate key in this recording",
            "timing": "hit_compile_us and hit_link_us sum observed costs at hit positions; these are ceilings, not predicted speedups",
            "limits": "Trace logging perturbs timings; key correctness and cross-runtime sharing are unproven. Self-hosted source text is unavailable in this trace, so its exact-key comparison relies on bytecode and metadata. Sizes exclude allocator overhead, JitCode GC cells, IC stubs, profiling metadata, and any relocation or indirection machinery. Browser setup and browser code remain in the trace.",
        }, output, separators=(",", ":"))
        output.write(',"workloads":{')
        for index, variant in enumerate(sorted(latest)):
            if index:
                output.write(",")
            json.dump(variant, output)
            output.write(":")
            json.dump(analyze_record(latest[variant]), output, separators=(",", ":"))
        output.write("}}\n")

    render(destination, output_dir / "index.html")


if __name__ == "__main__":
    main()
