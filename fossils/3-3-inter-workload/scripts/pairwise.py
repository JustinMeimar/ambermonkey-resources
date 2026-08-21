"""Shared pairwise-intersection helpers for the 3-3 inter-workload fossil.

The reduce/analyze layer is the same for every downstream artifact
(summary JSON, paper matrix tables, and figures), so both static and
dynamic intersection are computed here from the pooled per-site records.
"""

import json
import os
import sys
from collections import Counter

SITES = (
    "amazon", "bing-search", "buzzfeed", "cnn",
    "ebay", "espn", "expedia", "facebook",
)

SITE_LABELS = {
    "amazon": "Amazon",
    "bing-search": "Bing Search",
    "buzzfeed": "BuzzFeed",
    "cnn": "CNN",
    "ebay": "eBay",
    "espn": "ESPN",
    "expedia": "Expedia",
    "facebook": "Facebook",
}

RECORDS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "records"
)


def latest_record_per_site(records_dir=RECORDS_DIR):
    latest = {}
    for entry in sorted(os.listdir(records_dir)):
        parts = entry.split("_")
        site = "_".join(parts[3:-1])
        if site in SITES:
            latest[site] = entry
    missing = [site for site in SITES if site not in latest]
    if missing:
        sys.exit(f"missing sites: {missing}")
    return latest


def load_counters(records_dir=RECORDS_DIR, latest=None):
    latest = latest or latest_record_per_site(records_dir)
    ic_sets, ic_freqs, bl_sets, bl_freqs = {}, {}, {}, {}
    for site in SITES:
        path = os.path.join(records_dir, latest[site], "results.json")
        with open(path) as fh:
            record = json.load(fh)
        ic_req = Counter()
        ic_ent = Counter()
        bl_comp = Counter()
        bl_ent = Counter()
        for obs in record.get("observations", []):
            stdout = obs.get("stdout")
            if isinstance(stdout, list):
                stdout = "\n".join(stdout)
            payload = json.loads(stdout.strip())
            ic_c = ((payload.get("ic") or {}).get("content") or {})
            bl_c = ((payload.get("baseline") or {}).get("content") or {})
            ic_req.update({k: int(v) for k, v in ic_c.get("attaches", {}).items()})
            ic_ent.update({k: int(v) for k, v in ic_c.get("entered", {}).items()})
            bl_comp.update({k: int(v) for k, v in bl_c.get("compiles", {}).items()})
            bl_ent.update({k: int(v) for k, v in bl_c.get("entered", {}).items()})
        ic_sets[site] = set(ic_req)
        ic_freqs[site] = ic_ent
        bl_sets[site] = set(bl_comp)
        bl_freqs[site] = bl_ent
    return ic_sets, ic_freqs, bl_sets, bl_freqs


def static_intersection(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def dynamic_intersection(source_set, target_freq):
    total = sum(target_freq.values())
    if not total:
        return 0.0
    return sum(count for identity, count in target_freq.items() if identity in source_set) / total


def matrix(fn, rows, cols):
    return [[fn(rows[a], cols[b]) for b in SITES] for a in SITES]


def render_matrix_table(matrix_values, *, row_label):
    """Return a table-from-json payload for an 8x8 pairwise matrix.

    Cells are pre-formatted percent strings so the diagonal can carry
    a dash without confusing the paper-side formatter.
    """
    columns = [
        {"key": "row", "label": row_label, "align": "left", "format": "str"}
    ]
    for site in SITES:
        columns.append({
            "key": site,
            "label": SITE_LABELS[site],
            "align": "right",
            "format": "str",
        })
    rows = []
    for i, site_a in enumerate(SITES):
        row = [SITE_LABELS[site_a]]
        for j, _ in enumerate(SITES):
            if i == j:
                row.append("—")
            else:
                row.append(f"{matrix_values[i][j] * 100:.1f}%")
        rows.append(row)
    return {
        "columns": columns,
        "rows": rows,
        "text_size": 7,
        "cell_inset": 3,
    }
