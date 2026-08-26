"""Shared pairwise-intersection helpers for the 3-3 inter-workload fossil.

Sites are discovered from records/ ∩ variants declared in fossil.toml, so
adding or removing a variant needs no code change. All downstream artifacts
(summary JSON, paper matrix tables, figures) share the reduce/analyze layer.
"""

import json
import os
import sys
from collections import Counter

try:
    import tomllib
except ImportError:
    import tomli as tomllib

FOSSIL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RECORDS_DIR = os.path.join(FOSSIL_DIR, "records")
FOSSIL_TOML = os.path.join(FOSSIL_DIR, "fossil.toml")

# Display-name overrides for site slugs whose default title-casing is wrong.
_LABEL_OVERRIDES = {
    "bing-search":   "Bing",
    "buzzfeed":      "BuzzFeed",
    "cnn":           "CNN",
    "ebay":          "eBay",
    "espn":          "ESPN",
    "google-docs":   "G. Docs",
    "google-mail":   "G. Mail",
    "google-search": "G. Search",
    "google-slides": "G. Slides",
    "imdb":          "IMDb",
    "linkedin":      "LinkedIn",
    "nytimes":       "NY Times",
    "paypal":        "PayPal",
    "yahoo-mail":    "Y. Mail",
    "youtube":       "YouTube",
}


def site_label(slug):
    if slug in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[slug]
    return " ".join(part.capitalize() for part in slug.split("-"))


def declared_variants(fossil_toml=FOSSIL_TOML):
    with open(fossil_toml, "rb") as fh:
        return tuple((tomllib.load(fh).get("variants") or {}).keys())


def discover_sites(records_dir=RECORDS_DIR, fossil_toml=FOSSIL_TOML):
    """Sites are the alphabetically-sorted intersection of declared variants
    and site slugs found in records/. Stale runs from earlier variant sets
    are ignored so the tables and figures always reflect the current fossil."""
    declared = set(declared_variants(fossil_toml))
    seen = set()
    for entry in os.listdir(records_dir):
        parts = entry.split("_")
        if len(parts) < 5:
            continue
        site = "_".join(parts[3:-1])
        if site in declared:
            seen.add(site)
    return tuple(sorted(seen))


def latest_record_per_site(records_dir=RECORDS_DIR, sites=None):
    sites = tuple(sites) if sites is not None else discover_sites(records_dir)
    latest = {}
    for entry in sorted(os.listdir(records_dir)):
        parts = entry.split("_")
        if len(parts) < 5:
            continue
        site = "_".join(parts[3:-1])
        if site in sites:
            latest[site] = entry
    missing = [site for site in sites if site not in latest]
    if missing:
        sys.exit(f"missing sites: {missing}")
    return sites, latest


def load_counters(records_dir=RECORDS_DIR, sites=None):
    sites, latest = latest_record_per_site(records_dir, sites)
    ic_sets, ic_freqs, bl_sets, bl_freqs = {}, {}, {}, {}
    for site in sites:
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
        if not ic_req or not bl_comp:
            # Stale record predates the current emit_ranks.py schema; rebury.
            sys.exit(
                f"{site}: latest record {latest[site]} has empty "
                f"ic/baseline counters — rebury this variant"
            )
        ic_sets[site] = set(ic_req)
        ic_freqs[site] = ic_ent
        bl_sets[site] = set(bl_comp)
        bl_freqs[site] = bl_ent
    return sites, ic_sets, ic_freqs, bl_sets, bl_freqs


def static_intersection(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def dynamic_intersection(source_set, target_freq):
    total = sum(target_freq.values())
    if not total:
        return 0.0
    return sum(count for identity, count in target_freq.items() if identity in source_set) / total


def matrix(fn, rows, cols, sites):
    return [[fn(rows[a], cols[b]) for b in sites] for a in sites]


def render_matrix_table(matrix_values, sites, *, row_label):
    """Return a table-from-json payload for an NxN pairwise matrix.

    Cells are pre-formatted percent strings so the diagonal can carry
    a dash without confusing the paper-side formatter.
    """
    columns = [
        {"key": "row", "label": row_label, "align": "left", "format": "str"}
    ]
    for site in sites:
        columns.append({
            "key": site,
            "label": site_label(site),
            "align": "right",
            "format": "str",
        })
    rows = []
    n = len(sites)
    for i in range(n):
        row = [site_label(sites[i])]
        for j in range(n):
            if i == j:
                row.append("—")
            else:
                row.append(f"{matrix_values[i][j] * 100:.1f}%")
        rows.append(row)
    # Compact text for larger matrices so a 24x24 still fits page width.
    text_size = 7 if n <= 8 else max(4, 7 - (n - 8) // 4)
    cell_inset = 3 if n <= 8 else max(1, 3 - (n - 8) // 6)
    return {
        "columns": columns,
        "rows": rows,
        "text_size": text_size,
        "cell_inset": cell_inset,
    }
