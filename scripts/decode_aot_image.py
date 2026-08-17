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

# Configuration field layouts. Field order and padding match GenerateAOTImage.py
# lay_out() applied to the yaml schema at the tagged git revision.
CONFIG_V1_FMT = "<BBBB III"
CONFIG_V1_FIELDS = (
    "disableInlining",
    "spectreObjectMitigations",
    "spectreStringMitigations",
    "baselineBatching",
    "baselineJitWarmUpThreshold",
    "baselineQueueCapacity",
    "trialInliningWarmUpThreshold",
)
assert struct.calcsize(CONFIG_V1_FMT) == 16

CONFIG_V2_FMT = "<BBBBB3x III"
CONFIG_V2_FIELDS = (
    "disableInlining",
    "spectreIndexMasking",
    "spectreObjectMitigations",
    "spectreStringMitigations",
    "baselineBatching",
    "baselineJitWarmUpThreshold",
    "baselineQueueCapacity",
    "trialInliningWarmUpThreshold",
)
assert struct.calcsize(CONFIG_V2_FMT) == 20

# V3 keeps the 20-byte size: the two new u8 flags (baselineJit,
# enableICFramePointers) consume two bytes of the old 3-byte trailing padding,
# leaving one byte of padding before the u32 thresholds.
CONFIG_V3_FMT = "<BBBBBBB1x III"
CONFIG_V3_FIELDS = (
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
assert struct.calcsize(CONFIG_V3_FMT) == 20


def is_v3_layout(fields_bytes):
    # V2 and V3 share the 20-byte size. Disambiguate by peeking at the two
    # bytes that were padding in V2 (offsets 5 and 6). Any non-zero there means
    # the recorder wrote V3 fields; V2 leaves the whole span as zero padding.
    return fields_bytes[5] != 0 or fields_bytes[6] != 0


def decode_config_fields(size, fields_bytes):
    if size == 16:
        fmt, names, tag = CONFIG_V1_FMT, CONFIG_V1_FIELDS, "pre-indexMasking"
    elif size == 20:
        if is_v3_layout(fields_bytes):
            fmt, names, tag = CONFIG_V3_FMT, CONFIG_V3_FIELDS, "with baselineJit"
        else:
            fmt, names, tag = CONFIG_V2_FMT, CONFIG_V2_FIELDS, "with indexMasking"
    else:
        return None
    return tag, dict(zip(names, struct.unpack(fmt, fields_bytes)))


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
        result = decode_config_fields(fields_size, fields)
        if result is None:
            print(f"  fields        (unknown Configuration layout, size {fields_size})")
        else:
            tag, values = result
            print(f"  fields        Configuration [{tag}]")
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
