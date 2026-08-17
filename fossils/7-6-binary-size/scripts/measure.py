#!/usr/bin/env python3
"""PT_LOAD and AOT-image bytes for release libxul.so / firefox.
Dispatches on FOSSIL_TABLE_NAME: `libxul` (engine view) or `browser` (whole dist/bin)."""

import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_BUILD = Path("/home/justin/spidermonkey/firefox/build-browser-release")
AOT_BUILD = Path("/home/justin/spidermonkey/firefox/build-browser-release-aot")
DEFAULT_LIBXUL = DEFAULT_BUILD / "dist/bin/libxul.so"
AOT_LIBXUL = AOT_BUILD / "dist/bin/libxul.so"
DEFAULT_FIREFOX = DEFAULT_BUILD / "dist/bin/firefox"
AOT_FIREFOX = AOT_BUILD / "dist/bin/firefox"
DEFAULT_DIST_BIN = DEFAULT_BUILD / "dist/bin"
AOT_DIST_BIN = AOT_BUILD / "dist/bin"
AOT_PACKED_IMAGE = AOT_BUILD / "js/src/jit/aot/AOTImage.inc"
SELECTED_CORPUS_ENV = "SELECTED_CORPUS_DIR"
SELECTED_CORPUS_DEFAULT = Path("/tmp/amber-aot-corpus-selected")

LIBXUL_COLUMNS = [
    {"key": "configuration",      "label": "Configuration",      "align": "left",  "format": "str"},
    {"key": "pt_load_bytes",      "label": "PT_LOAD bytes",      "align": "right", "format": "int"},
    {"key": "corpus_files_bytes", "label": "Corpus-file bytes",  "align": "right", "format": "int"},
    {"key": "packed_image_bytes", "label": "Packed-image bytes", "align": "right", "format": "int"},
    {"key": "linked_image_bytes", "label": "Linked-image bytes", "align": "right", "format": "int"},
]

BROWSER_COLUMNS = [
    {"key": "configuration",     "label": "Configuration",       "align": "left",  "format": "str"},
    {"key": "firefox_bin_bytes", "label": "firefox launcher",    "align": "right", "format": "int"},
    {"key": "libxul_file_bytes", "label": "libxul.so on disk",   "align": "right", "format": "int"},
    {"key": "libxul_pt_load",    "label": "libxul PT_LOAD",      "align": "right", "format": "int"},
    {"key": "dist_bin_bytes",    "label": "dist/bin total",      "align": "right", "format": "int"},
    {"key": "dist_bin_files",    "label": "dist/bin file count", "align": "right", "format": "int"},
]


def die(msg):
    sys.exit(f"measure: {msg}")


def file_bytes(path):
    if not path.is_file():
        die(f"{path} does not exist")
    return path.stat().st_size


def sum_pt_load_bytes(libxul):
    if not libxul.is_file():
        die(f"{libxul} does not exist")
    out = subprocess.run(
        ["readelf", "-Wl", str(libxul)],
        capture_output=True, text=True, check=True,
    ).stdout
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] != "LOAD":
            continue
        total += int(parts[4], 16)
    if total == 0:
        die(f"no PT_LOAD segments in {libxul}")
    return total


def linked_image_bytes(libxul):
    out = subprocess.run(
        ["nm", str(libxul)],
        capture_output=True, text=True, check=True,
    ).stdout
    start = end = None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        if parts[-1] == "aot_image_start":
            start = int(parts[0], 16)
        elif parts[-1] == "aot_image_end":
            end = int(parts[0], 16)
    if start is None or end is None:
        die(f"aot_image_{{start,end}} symbols not found in {libxul}")
    return end - start


def selected_corpus_dir():
    override = os.environ.get(SELECTED_CORPUS_ENV)
    if override:
        return Path(override)
    return SELECTED_CORPUS_DEFAULT


def corpus_files_bytes():
    d = selected_corpus_dir()
    if not d.is_dir():
        return 0
    total = 0
    for root, _dirs, files in os.walk(d):
        rp = Path(root)
        for name in files:
            try:
                total += (rp / name).stat().st_size
            except FileNotFoundError:
                pass
    return total


def dist_bin_totals(dist_bin):
    if not dist_bin.is_dir():
        die(f"{dist_bin} is not a directory")
    total_bytes = 0
    file_count = 0
    for root, _dirs, files in os.walk(dist_bin):
        rp = Path(root)
        for name in files:
            try:
                total_bytes += (rp / name).stat().st_size
                file_count += 1
            except FileNotFoundError:
                pass
    return total_bytes, file_count


def build_libxul_table():
    default_pt_load = sum_pt_load_bytes(DEFAULT_LIBXUL)
    aot_pt_load = sum_pt_load_bytes(AOT_LIBXUL)
    aot_linked = linked_image_bytes(AOT_LIBXUL)
    aot_packed = file_bytes(AOT_PACKED_IMAGE)
    aot_corpus = corpus_files_bytes()
    rows = [
        ["Default JIT", default_pt_load, 0, 0, 0],
        ["Default JIT + AOT", aot_pt_load, aot_corpus, aot_packed, aot_linked],
    ]
    return {"columns": LIBXUL_COLUMNS, "rows": rows}


def build_browser_table():
    default_dist_bytes, default_dist_files = dist_bin_totals(DEFAULT_DIST_BIN)
    aot_dist_bytes, aot_dist_files = dist_bin_totals(AOT_DIST_BIN)
    rows = [
        [
            "Default JIT",
            file_bytes(DEFAULT_FIREFOX),
            file_bytes(DEFAULT_LIBXUL),
            sum_pt_load_bytes(DEFAULT_LIBXUL),
            default_dist_bytes,
            default_dist_files,
        ],
        [
            "Default JIT + AOT",
            file_bytes(AOT_FIREFOX),
            file_bytes(AOT_LIBXUL),
            sum_pt_load_bytes(AOT_LIBXUL),
            aot_dist_bytes,
            aot_dist_files,
        ],
    ]
    return {"columns": BROWSER_COLUMNS, "rows": rows}


TABLES = {
    "libxul": build_libxul_table,
    "browser": build_browser_table,
    # Retain the pre-split name for compatibility with the fossil.toml
    # entry that shipped first.
    "sizes": build_libxul_table,
}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    name = os.environ.get("FOSSIL_TABLE_NAME") or "libxul"
    builder = TABLES.get(name)
    if builder is None:
        die(f"unknown FOSSIL_TABLE_NAME={name!r}; valid: {sorted(TABLES)}")
    output = builder()
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
