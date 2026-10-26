#!/usr/bin/env python3
"""PT_LOAD and AOT-image bytes for release libxul.so / firefox."""

import json
import os
import subprocess
import struct
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "common"))
from settings import BIN_RELEASE, BIN_AOT, SELECTED_CORPUS

DEFAULT_BUILD = BIN_RELEASE.parents[2]
AOT_BUILD = BIN_AOT.parents[2]
DEFAULT_LIBXUL = DEFAULT_BUILD / "dist/bin/libxul.so"
AOT_LIBXUL = AOT_BUILD / "dist/bin/libxul.so"
DEFAULT_FIREFOX = DEFAULT_BUILD / "dist/bin/firefox"
AOT_FIREFOX = AOT_BUILD / "dist/bin/firefox"
DEFAULT_DIST_BIN = DEFAULT_BUILD / "dist/bin"
AOT_DIST_BIN = AOT_BUILD / "dist/bin"
AOT_PACKED_IMAGE = AOT_BUILD / "js/src/jit/aot/AOTImage.inc"

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


def image_bounds(libxul):
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
    return start, end


def linked_image_bytes(libxul):
    start, end = image_bounds(libxul)
    return end - start


def embedded_image(libxul):
    start, end = image_bounds(libxul)
    with libxul.open('rb') as stream:
        header = stream.read(64)
        if header[:6] != b'\x7fELF\x02\x01':
            die('expected a little-endian ELF64 library')
        phoff = struct.unpack_from('<Q', header, 32)[0]
        size, count = struct.unpack_from('<HH', header, 54)
        for index in range(count):
            stream.seek(phoff + index * size)
            entry = stream.read(size)
            kind, flags, offset, address, physical, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', entry)
            if kind == 1 and address <= start < end <= address + filesz:
                stream.seek(offset + start - address)
                data = stream.read(end - start)
                if data[:4] != b'AOTI' or len(data) < 36:
                    die('invalid embedded image header')
                image_size = struct.unpack_from('<I', data, 32)[0]
                if not 36 <= image_size <= len(data):
                    die('embedded image extends outside its symbols')
                return data[:image_size]
    die('image symbols do not fall inside a file-backed LOAD segment')


def build_image_table():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
    from aot_image_stats import parse_image
    with tempfile.TemporaryDirectory() as directory:
        image = Path(directory) / 'linked-image.bin'
        image.write_bytes(embedded_image(AOT_LIBXUL))
        stats, _ = parse_image(image)
    stats['source'] = str(AOT_LIBXUL) + '#aot_image_start'
    stats['representation'] = 'linked image; relocations differ from the original packed input'
    return stats


def corpus_files_bytes():
    d = SELECTED_CORPUS
    if not d.is_dir():
        return None
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
    aot_packed = file_bytes(AOT_PACKED_IMAGE) if AOT_PACKED_IMAGE.is_file() else len(embedded_image(AOT_LIBXUL))
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
    columns = list(BROWSER_COLUMNS)
    release_manifest = os.environ.get('AMBERMONKEY_RELEASE_MANIFEST')
    if release_manifest:
        releases = json.loads(Path(release_manifest).read_text())
        columns.append({'key': 'archive_bytes', 'label': 'Compressed package bytes', 'align': 'right', 'format': 'int'})
        for row, release in zip(rows, ('default-browser-release', 'am-browser-release-tp6')):
            row.append(releases[release]['archive_bytes'])
    return {"columns": columns, "rows": rows}


def emit(builder, destination):
    destination.write_text(json.dumps(builder(), indent=2) + "\n")
