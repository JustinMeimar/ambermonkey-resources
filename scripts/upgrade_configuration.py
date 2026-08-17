#!/usr/bin/env python3
"""Upgrade configuration.aotb files under corpi/ to the current schema (v3).

Layout target (see AOTImageSchema.yaml Configuration blob):

  offset 0  disableInlining          (u8)
  offset 1  spectreIndexMasking      (u8)
  offset 2  spectreObjectMitigations (u8)
  offset 3  spectreStringMitigations (u8)
  offset 4  baselineBatching         (u8)
  offset 5  baselineJit              (u8)
  offset 6  enableICFramePointers    (u8)
  offset 7  padding                  (1 byte)
  offset 8  baselineJitWarmUpThreshold   (u32)
  offset 12 baselineQueueCapacity        (u32)
  offset 16 trialInliningWarmUpThreshold (u32)

Total fields size: 20 bytes.

New-field values assume the recording was done in the browser (both tp6
sites and the oracle recordings): the browser turns on indexMasking via
pref, baselineJit defaults to true, and IONPERF isn't set so
enableICFramePointers is false. Override at the command line if that
assumption ever stops holding.
"""

import argparse
import struct
import sys
from pathlib import Path

BLOB_FILE_MAGIC = 0x42544F41
BLOB_FILE_FMT = "<IHHII20sIIIII"
BLOB_FILE_HEADER_SIZE = struct.calcsize(BLOB_FILE_FMT)
CONFIG_KIND = 3

V1_FIELDS_SIZE = 16
V1_FMT = "<BBBB III"

V2_FIELDS_SIZE = 20
V2_FMT = "<BBBBB3x III"

V3_FIELDS_SIZE = 20
V3_FMT = "<BBBBBBB1x III"


def is_v3(fields):
    return fields[5] != 0 or fields[6] != 0


def read_header(data):
    return struct.unpack(BLOB_FILE_FMT, data[:BLOB_FILE_HEADER_SIZE])


def repack_header(hdr, fields_size):
    magic, version, reserved, kind, probe, ident, _, arrays, code, links, slot = hdr
    return struct.pack(
        BLOB_FILE_FMT,
        magic, version, reserved, kind, probe, ident,
        fields_size, arrays, code, links, slot,
    )


def upgrade(path, spectre_index, baseline_jit, ic_frame_pointers, dry_run):
    data = path.read_bytes()
    if len(data) < BLOB_FILE_HEADER_SIZE:
        return f"skip (truncated, {len(data)} bytes)"
    hdr = read_header(data)
    magic, _, _, kind, _, _, fields_size, arrays, code, links, _ = hdr
    if magic != BLOB_FILE_MAGIC:
        return f"skip (bad magic {magic:#x})"
    if kind != CONFIG_KIND:
        return f"skip (kind {kind}, not Configuration)"
    fields = data[BLOB_FILE_HEADER_SIZE:BLOB_FILE_HEADER_SIZE + fields_size]

    if fields_size == V1_FIELDS_SIZE:
        (disable_inlining, spectre_object, spectre_string, baseline_batching,
         warmup, queue_cap, trial_warmup) = struct.unpack(V1_FMT, fields)
    elif fields_size == V2_FIELDS_SIZE:
        if is_v3(fields):
            return "skip (already v3)"
        (disable_inlining, spectre_index_recorded, spectre_object,
         spectre_string, baseline_batching, warmup, queue_cap,
         trial_warmup) = struct.unpack(V2_FMT, fields)
        # Preserve the value the recorder wrote; only fall back to the
        # heuristic default when the source was pre-v2.
        spectre_index = spectre_index_recorded
    else:
        return f"skip (unknown fields size {fields_size})"

    new_fields = struct.pack(
        V3_FMT,
        disable_inlining,
        spectre_index,
        spectre_object,
        spectre_string,
        baseline_batching,
        baseline_jit,
        ic_frame_pointers,
        warmup,
        queue_cap,
        trial_warmup,
    )
    assert len(new_fields) == V3_FIELDS_SIZE
    new_data = repack_header(hdr, V3_FIELDS_SIZE) + new_fields + data[BLOB_FILE_HEADER_SIZE + fields_size:]
    if dry_run:
        return f"would upgrade v{1 if fields_size == V1_FIELDS_SIZE else 2} -> v3 ({len(data)} -> {len(new_data)} bytes)"
    path.write_bytes(new_data)
    return f"upgraded v{1 if fields_size == V1_FIELDS_SIZE else 2} -> v3 ({len(data)} -> {len(new_data)} bytes)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", type=Path,
                    help="directory to walk for configuration.aotb files")
    ap.add_argument("--spectre-index-masking", type=int, choices=(0, 1), default=1,
                    help="value for spectreIndexMasking when upgrading from v1 (default: 1, browser pref)")
    ap.add_argument("--baseline-jit", type=int, choices=(0, 1), default=1,
                    help="value for baselineJit (default: 1, browser default)")
    ap.add_argument("--enable-ic-frame-pointers", type=int, choices=(0, 1), default=0,
                    help="value for enableICFramePointers (default: 0, no IONPERF)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen without touching files")
    args = ap.parse_args()

    if not args.root.is_dir():
        sys.exit(f"{args.root} is not a directory")

    paths = sorted(args.root.rglob("configuration.aotb"))
    if not paths:
        sys.exit(f"no configuration.aotb under {args.root}")

    for p in paths:
        result = upgrade(
            p,
            spectre_index=args.spectre_index_masking,
            baseline_jit=args.baseline_jit,
            ic_frame_pointers=args.enable_ic_frame_pointers,
            dry_run=args.dry_run,
        )
        print(f"{p}: {result}")


if __name__ == "__main__":
    main()
