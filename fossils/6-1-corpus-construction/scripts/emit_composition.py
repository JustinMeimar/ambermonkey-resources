#!/usr/bin/env python3
"""Corpus-composition scalars plus a prevalence-pruning threshold sweep.
Reads $CORPUS per-site subdirs, train.txt, and the self-hosted dir.
Invoked as `fossil table composition`; arg 1 is the destination path."""

import json
import sys
from pathlib import Path

CORPUS_DIR = Path("/tmp/amber-aot-corpus")
SELFHOSTED_DIR = Path("/tmp/amber-aot-selfhosted")
FOSSIL_DIR = Path(__file__).resolve().parent.parent
TRAIN_FILE = FOSSIL_DIR / "train.txt"
TEST_FILE = FOSSIL_DIR / "test.txt"

ARTIFACT_SUFFIX = ".aotb"
IC_PREFIX = "ic-"
BLFUN_PREFIX = "blfun-"

BYTES_PER_KB = 1_000

THRESHOLDS = (1.0, 0.75, 0.5, 0.25, 0.10, 0.05, 0.0)

COLUMN_META = {
    "threshold": {"label": "Threshold",     "align": "right", "format": "percent"},
    "ic_stubs":  {"label": "IC bodies",     "align": "right", "format": "int"},
    "ic_kb":     {"label": "IC bodies (KB)", "align": "right", "format": "int"},
}
COLUMN_ORDER = ("threshold", "ic_stubs", "ic_kb")


def die(msg):
    sys.exit(f"emit_composition: {msg}")


def read_sites_file(path):
    names = []
    for raw in path.read_text().splitlines():
        s = raw.split("#", 1)[0].strip()
        if s:
            names.append(s)
    if not names:
        die(f"{path} lists no sites")
    return names


def ic_artifacts(site_dir):
    return [f for f in site_dir.iterdir()
            if f.name.startswith(IC_PREFIX) and f.name.endswith(ARTIFACT_SUFFIX)]


def count_self_hosted_functions(selfhosted_dir):
    if not selfhosted_dir.is_dir():
        die(f"{selfhosted_dir} is not a directory (record self-hosted first)")
    return sum(1 for p in selfhosted_dir.iterdir()
               if p.name.startswith(BLFUN_PREFIX) and p.name.endswith(ARTIFACT_SUFFIX))


def sweep_rows(seen_counts, seen_sizes, n_sites):
    rows = []
    for t in THRESHOLDS:
        min_sites = max(1, round(t * n_sites))
        eligible = [n for n, c in seen_counts.items() if c >= min_sites]
        eligible_bytes = sum(seen_sizes[n] for n in eligible)
        rows.append([t, len(eligible), round(eligible_bytes / BYTES_PER_KB)])
    return rows


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None

    train = read_sites_file(TRAIN_FILE)
    test = read_sites_file(TEST_FILE)

    missing = [s for s in train if not (CORPUS_DIR / s).is_dir()]
    if missing:
        die(f"listed training sites without a per-site subdir under {CORPUS_DIR}: "
            f"{', '.join(missing)}")

    seen_counts = {}
    seen_sizes = {}
    for site in train:
        for f in ic_artifacts(CORPUS_DIR / site):
            seen_counts[f.name] = seen_counts.get(f.name, 0) + 1
            seen_sizes[f.name] = f.stat().st_size

    union_count = len(seen_counts)
    union_bytes = sum(seen_sizes.values())
    singleton_names = [n for n, c in seen_counts.items() if c == 1]
    singleton_bytes = sum(seen_sizes[n] for n in singleton_names)
    recurrent_names = [n for n, c in seen_counts.items() if c >= 2]
    recurrent_bytes = sum(seen_sizes[n] for n in recurrent_names)

    output = {
        "train_site_count": len(train),
        "test_site_count": len(test),
        "total_site_count": len(train) + len(test),
        "self_hosted_function_count": count_self_hosted_functions(SELFHOSTED_DIR),
        "train_union_ic_count": union_count,
        "train_union_ic_bytes": union_bytes,
        "train_singleton_ic_count": len(singleton_names),
        "train_singleton_ic_bytes": singleton_bytes,
        "train_recurrent_ic_count": len(recurrent_names),
        "train_recurrent_ic_bytes": recurrent_bytes,
        "columns": [{"key": k, **COLUMN_META[k]} for k in COLUMN_ORDER],
        "rows": sweep_rows(seen_counts, seen_sizes, len(train)),
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(output, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
