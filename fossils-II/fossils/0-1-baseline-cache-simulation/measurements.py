"""Measurements of completed guest Baseline installations within one recording."""

from collections import Counter, defaultdict


WORKLOADS = ("speedometer3", "jetstream3", "tp6")
LABELS = {"speedometer3": "Speedometer 3", "jetstream3": "JetStream 3", "tp6": "TP6"}
SCOPES = ("first", "same_runtime", "same_process", "cross_process")
METHOD = {
    "population": "Guest Baseline installations with a source fingerprint; one latest recording per workload.",
    "identity": "Candidate key: filename, source span, source encoding, source and bytecode hashes, immutable flags, and debug instrumentation. This is not proven native-code equivalence.",
    "recurrence": "An installation repeats if its key appeared earlier in the same recording. Scope compares only the immediately preceding matching installation.",
    "timing": "Gaps are wall-clock intervals between matching installations, not execution intervals. Compile work is recorded backend duration; logging perturbs it and overlapping work is not elapsed time saved.",
    "sources": "Exact recorded filenames group installations. Labels abbreviate local origins for display only; CSV retains full filenames. Source text itself was not recorded.",
    "selection": "Latest record directory by Fossil record ID for each of speedometer3, jetstream3, tp6. Failed or multi-observation records fail explicitly; no silent fallback. Manual browsing is excluded.",
}


def measure(workload):
    installs = [e for e in workload["events"] if e["event"] == "install" and "key_id" in e]
    if not installs:
        raise ValueError("recording contains no eligible guest installations")
    origin = installs[0]["elapsed_us"]
    timeline = defaultdict(lambda: {"first": 0, "repeat": 0})
    sources = {}
    repeat_compile = total_compile = linked_repeats = 0
    for e in installs:
        repeat = e["recurrence_scope"] != "first"
        timeline[(e["elapsed_us"] - origin) // 1_000_000]["repeat" if repeat else "first"] += 1
        row = sources.setdefault(e["filename"], {
            "filename": e["filename"], "keys": set(), "installs": 0,
            "repeats": 0, "compile_us": 0, "repeat_compile_us": 0,
        })
        row["keys"].add(e["key_id"])
        row["installs"] += 1
        row["repeats"] += repeat
        compile_us = e.get("compile_us", 0)
        row["compile_us"] += compile_us
        row["repeat_compile_us"] += compile_us if repeat else 0
        total_compile += compile_us
        repeat_compile += compile_us if repeat else 0
        linked_repeats += repeat and "compile_us" in e
    source_rows = []
    for row in sources.values():
        row["keys"] = len(row["keys"])
        row["repeat_share"] = row["repeats"] / max(1, len(installs) - workload["candidate"]["keys"])
        row["repeat_compile_share"] = row["repeat_compile_us"] / repeat_compile if repeat_compile else None
        source_rows.append(row)
    source_rows.sort(key=lambda row: (-row["repeats"], row["filename"]))
    multiplicity = Counter(row["installs"] for row in workload["keys"])
    return {
        "record_id": workload["record_id"],
        "manifest": workload["manifest"],
        "recording": workload["recording"],
        "firefox_revisions": sorted({e["firefox_revision"] for e in workload["events"] if e["event"] == "run" and "firefox_revision" in e}),
        "candidate": workload["candidate"],
        "compile_us": total_compile,
        "repeat_compile_us": repeat_compile,
        "linked_repeat_compiles": linked_repeats,
        "timeline_origin_after_runner_us": origin,
        "timeline": [{"second": second, **timeline[second]} for second in range(max(timeline) + 1)],
        "recurrence_gaps_us": sorted(e["recurrence_gap_us"] for e in installs if "recurrence_gap_us" in e),
        "multiplicity": [{"installs_per_key": n, "keys": count} for n, count in sorted(multiplicity.items())],
        "sources": source_rows,
    }
