#!/usr/bin/env python3
"""Reduce per-process Baseline and IC demand into artifact counters.
Baseline: compiles/entered keyed by semantic_id. IC: attaches/entered keyed by ic_body_id.
Guest scripts only; content streams must have lifecycle/IC/demand/baseline channels."""

import collections
import json
import os
import sys


INSTR_CH_LIFECYCLE = 1 << 0
INSTR_CH_IC = 1 << 1
INSTR_CH_DEMAND = 1 << 2
INSTR_CH_BASELINE = 1 << 6
REQUIRED_CHANNELS = (
    INSTR_CH_LIFECYCLE | INSTR_CH_IC | INSTR_CH_DEMAND | INSTR_CH_BASELINE
)
ACCEPTED_SOURCE_CLASS = "guest"


def die(message):
    print(f"emit_ranks: FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def script_class(state, script_id, context):
    source_class = state["script_classes"].get(script_id)
    if source_class is None:
        die(f"{context}: script {script_id} has no script-create event")
    return source_class


def baseline_identity(state, script_id, context):
    identity = state["baseline_by_script"].get(script_id)
    if identity is None:
        die(f"{context}: script {script_id} has no baseline-compile event")
    return identity


def parse(path, state):
    with open(path) as stream:
        for line in stream:
            if not any(
                kind in line
                for kind in (
                    '"run-header"',
                    '"script-create"',
                    '"baseline-compile"',
                    '"baseline-entries-retire"',
                    '"ic-instance-attach"',
                    '"ic-instance-detach"',
                    '"entries-flush"',
                )
            ):
                continue
            event = json.loads(line)
            kind = event["kind"]
            if kind == "run-header":
                if state["mode"] is not None:
                    die(f"{path}: duplicate run-header")
                state["mode"] = event.get("mode")
                state["channels"] = int(event.get("channels", 0))
            elif kind == "script-create":
                script_id = int(event["script_local_id"])
                source_class = event.get("source_class", "unknown")
                previous = state["script_classes"].setdefault(
                    script_id, source_class
                )
                if previous != source_class:
                    die(f"{path}: script {script_id} changed source class")
            elif kind == "baseline-compile":
                script_id = int(event["script_local_id"])
                identity = event["semantic_id"]
                previous = state["baseline_by_script"].setdefault(
                    script_id, identity
                )
                if previous != identity:
                    die(f"{path}: script {script_id} changed semantic identity")
                if script_class(state, script_id, path) == ACCEPTED_SOURCE_CLASS:
                    state["compiles_bl"][identity] += 1
            elif kind == "baseline-entries-retire":
                count = int(event.get("entered_count", 0))
                if not count:
                    continue
                script_id = int(event["script_local_id"])
                if script_class(state, script_id, path) != ACCEPTED_SOURCE_CLASS:
                    continue
                identity = baseline_identity(state, script_id, path)
                state["entered_bl"][identity] += count
                state["retired_baseline_rows"] += 1
            elif kind == "ic-instance-attach":
                script_id = int(event["script_local_id"])
                source_class = event.get("source_class", "unknown")
                known_class = script_class(state, script_id, path)
                if source_class != known_class:
                    die(f"{path}: IC attach source class disagrees with script")
                if source_class == ACCEPTED_SOURCE_CLASS:
                    state["attaches_ic"][event["ic_body_id"]] += 1
            elif kind == "ic-instance-detach":
                if event.get("is_fallback") or state["terminal_with_scripts"]:
                    continue
                count = int(event.get("entered_count", 0))
                if not count:
                    continue
                script_id = int(event["script_local_id"])
                if script_class(state, script_id, path) == ACCEPTED_SOURCE_CLASS:
                    state["entered_ic"][event["ic_body_id"]] += count
            elif kind == "entries-flush":
                if event.get("reason") != "runtime-shutdown":
                    continue
                runtime_id = int(event.get("rt", 0))
                if not runtime_id:
                    die(f"{path}: terminal entries-flush has no runtime id")
                if runtime_id in state["terminal_runtimes"]:
                    die(f"{path}: duplicate terminal flush for runtime {runtime_id}")
                state["terminal_runtimes"].add(runtime_id)
                state["flush_count"] += 1
                rows = event.get("scripts", []) or []
                if rows:
                    state["terminal_with_scripts"] = True
                for row in rows:
                    script_id = int(row["script_local_id"])
                    source_class = script_class(state, script_id, path)
                    count = int(row.get("entered_count", 0))
                    if count and source_class == ACCEPTED_SOURCE_CLASS:
                        identity = baseline_identity(state, script_id, path)
                        state["entered_bl"][identity] += count
                    if source_class != ACCEPTED_SOURCE_CLASS:
                        continue
                    for entry in row.get("ic_entries", []) or []:
                        if entry.get("is_fallback"):
                            continue
                        count = int(entry.get("entered_count", 0))
                        if count:
                            state["entered_ic"][entry["ic_body_id"]] += count

    if state["mode"] != "demand":
        die(f"{path}: expected demand mode, observed {state['mode']!r}")
    missing_channels = REQUIRED_CHANNELS & ~state["channels"]
    if missing_channels:
        die(
            f"{path}: missing required instrumentation channels "
            f"0x{missing_channels:x}"
        )


def new_proc_state():
    return {
        "mode": None,
        "channels": 0,
        "script_classes": {},
        "baseline_by_script": {},
        "attaches_ic": collections.Counter(),
        "compiles_bl": collections.Counter(),
        "entered_ic": collections.Counter(),
        "entered_bl": collections.Counter(),
        "terminal_runtimes": set(),
        "terminal_with_scripts": False,
        "flush_count": 0,
        "retired_baseline_rows": 0,
    }


def merge_state(destination, source):
    destination["attaches_ic"].update(source["attaches_ic"])
    destination["compiles_bl"].update(source["compiles_bl"])
    destination["entered_ic"].update(source["entered_ic"])
    destination["entered_bl"].update(source["entered_bl"])
    destination["flush_count"] += source["flush_count"]
    destination["retired_baseline_rows"] += source["retired_baseline_rows"]


def main(root):
    per_proc = {"content": new_proc_state()}

    file_count = 0
    for filename in sorted(os.listdir(root)):
        if not filename.endswith(".jsonl"):
            continue
        process = filename.split(".", 1)[0]
        if process not in per_proc:
            continue
        file_count += 1
        file_state = new_proc_state()
        parse(os.path.join(root, filename), file_state)
        if (
            process == "content"
            and (file_state["attaches_ic"] or file_state["compiles_bl"])
            and file_state["flush_count"] == 0
        ):
            die(
                f"{filename} requested artifacts but emitted no terminal "
                "entries-flush; dynamic counts would omit live artifacts"
            )
        merge_state(per_proc[process], file_state)

    if file_count == 0:
        die(f"no content .jsonl files in {root}")
    content = per_proc["content"]
    if not content["attaches_ic"]:
        die("no guest content-process IC attachment identities")
    if not content["compiles_bl"]:
        die("no guest content-process Baseline compilation identities")
    if not content["entered_ic"]:
        die("no guest content-process IC entry counts")
    if not content["entered_bl"]:
        die("no guest content-process Baseline entry counts")
    missing_ic = set(content["entered_ic"]) - set(content["attaches_ic"])
    if missing_ic:
        die(f"{len(missing_ic)} entered IC bodies were never attached")
    missing_bl = set(content["entered_bl"]) - set(content["compiles_bl"])
    if missing_bl:
        die(f"{len(missing_bl)} entered Baseline functions were never compiled")

    output = {"ic": {}, "baseline": {}, "diagnostics": {}}
    for process, state in per_proc.items():
        output["ic"][process] = {
            "attaches": dict(state["attaches_ic"]),
            "entered": dict(state["entered_ic"]),
        }
        output["baseline"][process] = {
            "compiles": dict(state["compiles_bl"]),
            "entered": dict(state["entered_bl"]),
        }
        output["diagnostics"][process] = {
            "terminal_flushes": state["flush_count"],
            "retired_baseline_rows": state["retired_baseline_rows"],
        }

    json.dump(output, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
