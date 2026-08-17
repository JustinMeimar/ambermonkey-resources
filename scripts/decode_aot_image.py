#!/usr/bin/env python3
"""Decode .aotb blob files: header, then fields for known blob kinds.

Layout must stay in sync with jit/AOTImage.h (AOTBlobFileHeader) and
jit/AOTImageSchema.yaml (per-blob fields POD).
"""

import struct
import sys
from pathlib import Path

BLOB_FILE_MAGIC = 0x42544F41  # "AOTB"
BLOB_FILE_FMT = "<IHHII20sIIIII"
BLOB_FILE_HEADER_SIZE = struct.calcsize(BLOB_FILE_FMT)
assert BLOB_FILE_HEADER_SIZE == 56

KINDS = {
    0: "BaselineInterpreter",
    1: "BaselineFunction",
    2: "InlineCacheStub",
    3: "Configuration",
}

# Configuration field layout. Field order and padding match GenerateAOTImage.py
# lay_out() applied to the current yaml schema.
CONFIG_FMT = "<BBBBBBB1x III"
CONFIG_FIELDS = (
    "disableInlining",
    "spectreIndexMasking",
    "spectreObjectMitigations",
    "spectreStringMitigations",
    "baselineBatching",
    "baselineJit",
    "enableICFramePointers",
    "baselineJitWarmUpThreshold",
    "baselineQueueCapacity",
    "trialInliningWarmUpThreshold",
)
CONFIG_SIZE = struct.calcsize(CONFIG_FMT)
assert CONFIG_SIZE == 20


def decode_config_fields(size, fields_bytes):
    if size != CONFIG_SIZE:
        return None
    return dict(zip(CONFIG_FIELDS, struct.unpack(CONFIG_FMT, fields_bytes)))


def decode(path):
    data = Path(path).read_bytes()
    if len(data) < BLOB_FILE_HEADER_SIZE:
        print(f"{path}: truncated ({len(data)} bytes)")
        return
    hdr = struct.unpack(BLOB_FILE_FMT, data[:BLOB_FILE_HEADER_SIZE])
    (magic, version, _reserved, kind, probe_hash, identity_hash,
     fields_size, arrays_size, code_size, link_sites_size, slot_table_hash) = hdr

    print(f"{path}")
    print(f"  magic         {magic:#010x} ({'AOTB' if magic == BLOB_FILE_MAGIC else 'BAD'})")
    print(f"  version       {version}")
    print(f"  kind          {kind} ({KINDS.get(kind, '?')})")
    print(f"  probeHash     {probe_hash:#010x}")
    print(f"  identityHash  {identity_hash.hex()}")
    print(f"  fieldsSize    {fields_size}")
    print(f"  arraysSize    {arrays_size}")
    print(f"  codeSize      {code_size}")
    print(f"  linkSitesSize {link_sites_size}")
    print(f"  slotTableHash {slot_table_hash:#010x}")
    print(f"  fileSize      {len(data)}")

    fields = data[BLOB_FILE_HEADER_SIZE:BLOB_FILE_HEADER_SIZE + fields_size]
    if kind == 3:
        values = decode_config_fields(fields_size, fields)
        if values is None:
            print(f"  fields        (unexpected Configuration size {fields_size}, expected {CONFIG_SIZE})")
        else:
            print(f"  fields        Configuration")
            for name, value in values.items():
                print(f"    {name:32}= {value}")
    elif fields_size:
        print(f"  fields        {fields.hex()}")


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <path.aotb> [...]")
    for p in sys.argv[1:]:
        decode(p)


if __name__ == "__main__":
    main()
