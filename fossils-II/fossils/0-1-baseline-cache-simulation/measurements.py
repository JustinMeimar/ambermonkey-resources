"""Measurements of completed guest Baseline installations within one recording."""

from collections import Counter, defaultdict


LABELS = {"speedometer3": "Speedometer 3", "jetstream3": "JetStream 3", "tp6": "TP6"}
WORKLOADS = tuple(LABELS)
SCOPES = ("first", "same_runtime", "same_process", "cross_process")
METHOD = {
    "population": "Guest Baseline installations with a source fingerprint; one latest recording per workload.",
    "identity": "Candidate key: filename, source span, source encoding, source and bytecode hashes, immutable flags, and debug instrumentation. This is not proven native-code equivalence.",
    "recurrence": "An installation repeats if its key appeared earlier in the same recording. Scope compares only the immediately preceding matching installation.",
    "timing": "Gaps are wall-clock intervals between matching installations, not execution intervals. Compile work is recorded backend duration; logging perturbs it and overlapping work is not elapsed time saved.",
    "sources": "Exact recorded filenames group installations. Labels abbreviate local origins for display only; CSV retains full filenames. Source text itself was not recorded.",
    "selection": "Latest record directory by Fossil record ID for each of speedometer3, jetstream3, tp6. Failed or multi-observation records fail explicitly; no silent fallback. Manual browsing is excluded.",
}


def source_summary(installs):
    sources = {}
    for event in installs:
        row = sources.setdefault(event["filename"], {
            "filename": event["filename"], "keys": set(), "installs": 0,
            "repeats": 0, "compile_us": 0, "repeat_compile_us": 0,
            "cache_bytes": 0,
        })
        repeat = event["recurrence_scope"] != "first"
        row["keys"].add(event["key_id"])
        row["installs"] += 1
        row["repeats"] += repeat
        row["compile_us"] += event.get("compile_us", 0)
        row["repeat_compile_us"] += event.get("compile_us", 0) if repeat else 0
        row["cache_bytes"] += event["cache_bytes"]
    repeats = sum(row["repeats"] for row in sources.values())
    repeat_compile = sum(row["repeat_compile_us"] for row in sources.values())
    for row in sources.values():
        row["keys"] = len(row["keys"])
        row["repeat_share"] = row["repeats"] / max(1, repeats)
        row["repeat_compile_share"] = row["repeat_compile_us"] / repeat_compile if repeat_compile else None
    return list(sources.values())


def measure(workload):
    installs = workload["installs"]
    if not installs:
        raise ValueError("recording contains no eligible guest installations")
    origin = installs[0]["elapsed_us"]
    timeline = defaultdict(lambda: {"first": 0, "repeat": 0})
    for event in installs:
        kind = "first" if event["recurrence_scope"] == "first" else "repeat"
        timeline[(event["elapsed_us"] - origin) // 1_000_000][kind] += 1
    sources = [{k: v for k, v in row.items() if k != "cache_bytes"}
               for row in workload["sources"]]
    sources.sort(key=lambda row: (-row["repeats"], row["filename"]))
    multiplicity = Counter(row["installs"] for row in workload["keys"])
    return {
        **{key: workload[key] for key in ("record_id", "manifest", "recording", "candidate")},
        "firefox_revisions": sorted({e["firefox_revision"] for e in workload["events"] if e["event"] == "run" and "firefox_revision" in e}),
        "compile_us": sum(row["compile_us"] for row in sources),
        "repeat_compile_us": sum(row["repeat_compile_us"] for row in sources),
        "linked_repeat_compiles": sum(e["recurrence_scope"] != "first" and "compile_us" in e for e in installs),
        "timeline_origin_after_runner_us": origin,
        "timeline": [{"second": second, **timeline[second]} for second in range(max(timeline) + 1)],
        "recurrence_gaps_us": sorted(e["recurrence_gap_us"] for e in installs if "recurrence_gap_us" in e),
        "multiplicity": [{"installs_per_key": n, "keys": count} for n, count in sorted(multiplicity.items())],
        "sources": sources,
    }
