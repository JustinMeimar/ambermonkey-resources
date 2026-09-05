#!/usr/bin/env python3
"""Extract paper-facing counts and byte totals from a packed AOT image.

The packed image is authoritative: its directory describes exactly the
artifacts shipped in the evaluated binary.  When --corpus is supplied, this
script also checks that the source .aotb files have matching artifact counts
and code sizes.
"""

import argparse
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path


IMAGE_MAGIC = 0x49544F41  # "AOTI"
IMAGE_HEADER_FMT = "<IHHIIIIIII"
IMAGE_HEADER_SIZE = struct.calcsize(IMAGE_HEADER_FMT)
DIRECTORY_ENTRY_FMT = "<II20sIIIII"
DIRECTORY_ENTRY_SIZE = struct.calcsize(DIRECTORY_ENTRY_FMT)

BLOB_MAGIC = 0x42544F41  # "AOTB"
BLOB_HEADER_FMT = "<IHHII20sIIIII"
BLOB_HEADER_SIZE = struct.calcsize(BLOB_HEADER_FMT)

KINDS = {
    0: "baseline_interpreter",
    1: "baseline_body",
    2: "ic_stub_body",
    3: "configuration",
}


def die(message):
    sys.exit(f"aot_image_stats: {message}")


def parse_image(path):
    data = path.read_bytes()
    if len(data) < IMAGE_HEADER_SIZE:
        die(f"{path}: truncated image")

    header = struct.unpack_from(IMAGE_HEADER_FMT, data)
    (
        magic,
        version,
        _reserved,
        blob_count,
        _fingerprint_offset,
        fingerprint_size,
        directory_offset,
        text_offset,
        text_size,
        image_size,
    ) = header
    if magic != IMAGE_MAGIC:
        die(f"{path}: bad image magic {magic:#010x}")
    if image_size != len(data):
        die(f"{path}: header size {image_size} differs from file size {len(data)}")
    if directory_offset + blob_count * DIRECTORY_ENTRY_SIZE > text_offset:
        die(f"{path}: artifact directory overlaps image text")

    counts = Counter()
    code_bytes = Counter()
    fields_bytes = 0
    arrays_bytes = 0
    artifacts = Counter()
    for index in range(blob_count):
        offset = directory_offset + index * DIRECTORY_ENTRY_SIZE
        entry = struct.unpack_from(DIRECTORY_ENTRY_FMT, data, offset)
        kind, _probe, _identity, text_rel, entry_text, data_rel, fields, arrays = entry
        if kind not in KINDS:
            die(f"{path}: directory entry {index} has unknown kind {kind}")
        if text_offset + text_rel + entry_text > image_size:
            die(f"{path}: directory entry {index} has out-of-bounds text")
        if data_rel + fields + arrays > text_offset:
            die(f"{path}: directory entry {index} has out-of-bounds metadata")
        name = KINDS[kind]
        counts[name] += 1
        code_bytes[name] += entry_text
        fields_bytes += fields
        arrays_bytes += arrays
        artifacts[(kind, _probe, _identity, entry_text, fields, arrays)] += 1

    directory_bytes = blob_count * DIRECTORY_ENTRY_SIZE
    metadata_bytes = IMAGE_HEADER_SIZE + fingerprint_size + directory_bytes
    metadata_bytes += fields_bytes + arrays_bytes
    artifact_code_bytes = sum(code_bytes.values())
    alignment_bytes = image_size - metadata_bytes - artifact_code_bytes
    if alignment_bytes < 0:
        die(f"{path}: decoded components exceed image size")

    stats = {
        "source": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "image_version": version,
        "image_bytes": image_size,
        "image_text_region_bytes": text_size,
        "metadata_bytes": metadata_bytes,
        "alignment_bytes": alignment_bytes,
        "counts": dict(counts),
        "code_bytes": dict(code_bytes),
    }
    return stats, artifacts


def parse_corpus(path):
    counts = Counter()
    code_bytes = Counter()
    artifacts = Counter()
    for blob in sorted(path.glob("*.aotb")):
        data = blob.read_bytes()
        if len(data) < BLOB_HEADER_SIZE:
            die(f"{blob}: truncated blob")
        header = struct.unpack_from(BLOB_HEADER_FMT, data)
        magic, _version, _reserved, kind, probe, identity = header[:6]
        fields_size = header[6]
        arrays_size = header[7]
        code_size = header[8]
        link_sites_size = header[9]
        if magic != BLOB_MAGIC:
            die(f"{blob}: bad blob magic {magic:#010x}")
        if kind not in KINDS:
            die(f"{blob}: unknown blob kind {kind}")
        name = KINDS[kind]
        counts[name] += 1
        code_bytes[name] += code_size
        expected_size = (
            BLOB_HEADER_SIZE
            + fields_size
            + arrays_size
            + code_size
            + link_sites_size
        )
        if len(data) != expected_size:
            die(f"{blob}: header components total {expected_size}, file has {len(data)} bytes")
        artifacts[(kind, probe, identity, code_size, fields_size, arrays_size)] += 1
    return counts, code_bytes, artifacts


def validate_corpus(stats, image_artifacts, corpus):
    counts, code_bytes, corpus_artifacts = parse_corpus(corpus)
    for name in KINDS.values():
        image_count = stats["counts"].get(name, 0)
        corpus_count = counts.get(name, 0)
        if image_count != corpus_count:
            die(
                f"{corpus}: {name} count {corpus_count} does not match "
                f"packed image count {image_count}"
            )
        image_code = stats["code_bytes"].get(name, 0)
        corpus_code = code_bytes.get(name, 0)
        if image_code != corpus_code:
            die(
                f"{corpus}: {name} code size {corpus_code} does not match "
                f"packed image size {image_code}"
            )
    if image_artifacts != corpus_artifacts:
        missing = image_artifacts - corpus_artifacts
        extra = corpus_artifacts - image_artifacts
        die(
            f"{corpus}: artifact identities differ from packed image "
            f"({sum(missing.values())} missing, {sum(extra.values())} extra)"
        )
    stats["corpus"] = str(corpus)


def tex_int(value):
    return f"{value:,}".replace(",", "{,}")


def rounded_kb(value):
    return round(value / 1_000)


def tex_kb(value):
    return f"{tex_int(rounded_kb(value))}\\,kB"


def tex_share(value, total):
    return f"{100 * value / total:.1f}\\%"


def render_tex(stats):
    counts = stats["counts"]
    code = stats["code_bytes"]
    total = stats["image_bytes"]
    metadata = stats["metadata_bytes"]
    alignment = stats["alignment_bytes"]
    rows = [
        "% Generated by ../scripts/aot_image_stats.py; do not edit.",
        f"% Packed-image SHA-256: {stats['sha256']}",
        f"\\newcommand{{\\icstubcount}}{{{tex_int(counts['ic_stub_body'])}}}",
        f"\\newcommand{{\\selfhostedcount}}{{{tex_int(counts['baseline_body'])}}}",
        f"\\newcommand{{\\icstubcodesize}}{{{tex_kb(code['ic_stub_body'])}}}",
        f"\\newcommand{{\\baselinebodycodesize}}{{{tex_kb(code['baseline_body'])}}}",
        f"\\newcommand{{\\baselineinterpretercodesize}}{{{tex_kb(code['baseline_interpreter'])}}}",
        f"\\newcommand{{\\imagemetadatasize}}{{{tex_kb(metadata)}}}",
        f"\\newcommand{{\\imagealignmentsize}}{{{tex_kb(alignment)}}}",
        f"\\newcommand{{\\aotimagekilobytes}}{{{tex_kb(total)}}}",
        f"\\newcommand{{\\corpuspacked}}{{{total / 1_000_000:.2f}\\,MB}}",
        f"\\newcommand{{\\icstubimageshare}}{{{tex_share(code['ic_stub_body'], total)}}}",
        f"\\newcommand{{\\baselinebodyimageshare}}{{{tex_share(code['baseline_body'], total)}}}",
        f"\\newcommand{{\\baselineinterpreterimageshare}}{{{tex_share(code['baseline_interpreter'], total)}}}",
        f"\\newcommand{{\\imagemetadatashare}}{{{tex_share(metadata, total)}}}",
        f"\\newcommand{{\\imagealignmentshare}}{{{tex_share(alignment, total)}}}",
    ]
    return "\n".join(rows) + "\n"


def write_text(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="packed AOTImage.inc")
    parser.add_argument("--corpus", type=Path, help="source corpus to validate")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--tex-output", type=Path)
    args = parser.parse_args()

    stats, image_artifacts = parse_image(args.image)
    if args.corpus:
        validate_corpus(stats, image_artifacts, args.corpus)
    if args.json_output:
        write_text(args.json_output, json.dumps(stats, indent=2) + "\n")
    if args.tex_output:
        write_text(args.tex_output, render_tex(stats))
    if not args.json_output and not args.tex_output:
        json.dump(stats, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
