#!/usr/bin/env python3
"""Reduce per-process instrumentation JSONL: content procs, guest scripts only.
Emits `attaches` (static inventory) and `entered` (stub-entry counts) per IC body."""

import collections
import json
import os
import sys


INCLUDED_SOURCE_CLASS = "guest"
KNOWN_SOURCE_CLASSES = {"guest", "self-hosted", "chrome", "privileged"}


def die(msg):
    print(f"emit_ranks: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def new_state():
    return {
        "script_class": {},
        "attaches_ic": collections.Counter(),
        "entered_ic": collections.Counter(),
        "source": collections.defaultdict(
            lambda: {
                "attach_events": 0,
                "attached_bodies": set(),
                "entry_count": 0,
            }
        ),
        "flush_count": 0,
    }


def source_class(state, script_id, context):
    cls = state["script_class"].get(script_id)
    if cls is None:
        die(f"{context}: script {script_id!r} has no prior script-create")
    if cls not in KNOWN_SOURCE_CLASSES:
        die(f"{context}: script {script_id!r} has unknown source_class {cls!r}")
    return cls


def record_attach(state, row):
    script_id = row["script_local_id"]
    mapped = source_class(state, script_id, "ic-instance-attach")
    direct = row.get("source_class")
    if direct != mapped:
        die(
            "ic-instance-attach source-class mismatch for script "
            f"{script_id!r}: attach={direct!r}, script-create={mapped!r}"
        )
    body_id = row["ic_body_id"]
    stats = state["source"][mapped]
    stats["attach_events"] += 1
    stats["attached_bodies"].add(body_id)
    if mapped == INCLUDED_SOURCE_CLASS:
        state["attaches_ic"][body_id] += 1


def record_entries(state, cls, entries):
    for entry in entries or []:
        if entry.get("is_fallback"):
            continue
        count = int(entry.get("entered_count", 0))
        if count < 0:
            die(f"negative entered_count for {entry.get('ic_body_id')!r}")
        if not count:
            continue
        body_id = entry["ic_body_id"]
        state["source"][cls]["entry_count"] += count
        if cls == INCLUDED_SOURCE_CLASS:
            state["entered_ic"][body_id] += count


def parse(path):
    state = new_state()
    with open(path) as stream:
        for line_number, line in enumerate(stream, 1):
            if not any(
                marker in line
                for marker in (
                    '"script-create"',
                    '"ic-instance-attach"',
                    '"ic-instance-detach"',
                    '"entries-flush"',
                )
            ):
                continue
            try:
                row = json.loads(line)
                kind = row["kind"]
                if kind == "script-create":
                    script_id = row["script_local_id"]
                    cls = row.get("source_class")
                    old = state["script_class"].setdefault(script_id, cls)
                    if old != cls:
                        die(
                            f"{path}:{line_number}: script {script_id!r} "
                            f"changed source class from {old!r} to {cls!r}"
                        )
                    if cls not in KNOWN_SOURCE_CLASSES:
                        die(
                            f"{path}:{line_number}: unknown source_class "
                            f"{cls!r} for script {script_id!r}"
                        )
                elif kind == "ic-instance-attach":
                    record_attach(state, row)
                elif kind == "ic-instance-detach":
                    cls = source_class(
                        state, row["script_local_id"], "ic-instance-detach"
                    )
                    record_entries(state, cls, [row])
                elif kind == "entries-flush":
                    state["flush_count"] += 1
                    for script in row.get("scripts", []) or []:
                        cls = source_class(
                            state,
                            script["script_local_id"],
                            "entries-flush",
                        )
                        record_entries(state, cls, script.get("ic_entries", []))
            except (KeyError, TypeError, ValueError) as exc:
                die(f"{path}:{line_number}: malformed event: {exc}")
    return state


def merge(destination, source):
    destination["attaches_ic"].update(source["attaches_ic"])
    destination["entered_ic"].update(source["entered_ic"])
    destination["flush_count"] += source["flush_count"]
    for cls, stats in source["source"].items():
        merged = destination["source"][cls]
        merged["attach_events"] += stats["attach_events"]
        merged["attached_bodies"].update(stats["attached_bodies"])
        merged["entry_count"] += stats["entry_count"]


def main(root):
    content = new_state()
    content_files = 0
    ignored_files = 0
    for filename in sorted(os.listdir(root)):
        if not filename.endswith(".jsonl"):
            continue
        proc = filename.split(".", 1)[0]
        if proc != "content":
            ignored_files += 1
            continue
        content_files += 1
        file_state = parse(os.path.join(root, filename))
        if file_state["attaches_ic"] and file_state["flush_count"] == 0:
            die(
                f"{filename} attached guest IC stubs but emitted no "
                "entries-flush; live-stub entry counts would be missing"
            )
        merge(content, file_state)

    if content_files == 0:
        die(f"no content-process .jsonl files in {root}")
    if not content["attaches_ic"]:
        die("no guest content-process IC attachments; instrumentation or classification failed")
    if content["flush_count"] == 0:
        die(
            "no content-process entries-flush events; JS_INSTR must include "
            "the demand channel and content shutdown must complete"
        )

    diagnostics = {}
    for cls in sorted(content["source"]):
        stats = content["source"][cls]
        diagnostics[cls] = {
            "attach_events": stats["attach_events"],
            "attached_bodies": len(stats["attached_bodies"]),
            "entry_count": stats["entry_count"],
        }

    out = {
        "ic": {
            "content": {
                "attaches": dict(content["attaches_ic"]),
                "entered": dict(content["entered_ic"]),
            }
        },
        "diagnostics": {
            "included_source_class": INCLUDED_SOURCE_CLASS,
            "content_files": content_files,
            "ignored_non_content_files": ignored_files,
            "entries_flushes": content["flush_count"],
            "by_source_class": diagnostics,
        },
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        die("usage: emit_ranks.py DIR")
    main(sys.argv[1])
