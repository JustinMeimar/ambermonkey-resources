#!/usr/bin/env python3

import sys
from collections import Counter
from pathlib import Path


def size(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}"
        n /= 1024


corpi = [Path(p) for p in sys.argv[1:]] or sorted(
    p for p in Path.cwd().iterdir() if p.is_dir() and not p.name.startswith(".")
)
rows = []
kinds = set()
for corpus in corpi:
    files = list(corpus.rglob("*.aotb"))
    counts = Counter(f.stem.split("-", 1)[0] for f in files)
    kinds.update(counts)
    rows.append((corpus.name, counts, len(files), sum(f.stat().st_size for f in files)))

kinds = sorted(kinds)
headers = ["corpus", *kinds, "artifacts", "size"]
table = [headers] + [
    [name, *(str(counts[k]) for k in kinds), str(total), size(bytes_)]
    for name, counts, total, bytes_ in rows
]
widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
for row in table:
    print("  ".join(value.ljust(widths[i]) if i == 0 else value.rjust(widths[i]) for i, value in enumerate(row)))
