"""Render self-contained figures and source tables from recorded measurements."""

from collections import Counter
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
from urllib.parse import urlsplit

from analyze_detail import analyze_record
from measurements import LABELS, METHOD, SCOPES, WORKLOADS, measure

FOSSIL = Path(__file__).resolve().parent
PROJECT = FOSSIL.parents[1]
COLORS = ("#b7c1c5", "#087f75", "#4675a5", "#c56b32")
CAPTIONS = {
    "recurrence": "Guest installations with source fingerprints. Scope is relative to the preceding matching candidate key within one recording. Percentages use all eligible installations; recurrence is not a measured cache hit rate.",
    "returns": "Guest installations with source fingerprints. Left: first and repeated installations in one-second bins, starting at the first eligible installation. Right: empirical CDF of intervals between consecutive matching installations; each repeat has equal weight. These are installation events, not calls to installed code.",
    "sources": "Guest installations with source fingerprints, grouped by exact filename. Top five sources ranked by repeat count; Other sources includes every remaining filename. Work share is the source's share of recorded backend compilation time associated with repeats, not elapsed time saved. Full source names and all rows are in CSV.",
    "multiplicity": "Guest installations with source fingerprints. Each candidate key contributes once at its total number of installations in this recording. Percentages use distinct keys, not installations. Matching keys do not establish native-code equivalence.",
}


def load_measurements():
    latest = {}
    for path in sorted((FOSSIL / "records").iterdir()):
        if not (path / "manifest.json").is_file():
            continue
        manifest = json.loads((path / "manifest.json").read_text())
        if manifest["variant"] in WORKLOADS:
            latest[manifest["variant"]] = path
    missing = set(WORKLOADS) - latest.keys()
    if missing:
        raise ValueError(f"missing workload recordings: {', '.join(sorted(missing))}")
    return {variant: measure(analyze_record(latest[variant])) for variant in WORKLOADS}


def plotting():
    python = PROJECT / ".venv/bin/python"
    if Path(sys.prefix).resolve() != python.parent.parent.resolve():
        if not python.is_file():
            raise SystemExit(f"Install figure dependencies: uv sync --project {PROJECT}")
        os.execv(python, [str(python), *sys.argv])
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ambermonkey-oopsla-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titleweight": "bold", "axes.labelcolor": "#303c40",
        "pdf.fonttype": 42,
    })
    return plt


def write_csv(path, rows, fields=None):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def finish(plt, fig, output, name, data, bottom=0.16):
    caption = CAPTIONS[name]
    fig.subplots_adjust(bottom=bottom)
    fig.text(0.03, 0.075, textwrap.fill(caption, 145), fontsize=8, va="bottom")
    exclusions = "; ".join(f"{LABELS[v]}: {data[v]['recording'].get('malformed', 0)}" for v in WORKLOADS)
    fig.text(0.03, 0.045, f"Malformed trace lines excluded — {exclusions}. Counts describe valid recorded events.", fontsize=7, color="#4f5b60")
    provenance = "Recordings: " + " | ".join(data[v]["record_id"] for v in WORKLOADS)
    fig.text(0.03, 0.02, provenance, fontsize=6.4, color="#4f5b60")
    fig.savefig(output / f"{name}.pdf", facecolor="white")
    plt.close(fig)


def recurrence(plt, output, data):
    fig, ax = plt.subplots(figsize=(11, 5))
    labels = ("First installation", "Same runtime", "Same process, other runtime", "Other process")
    rows = []
    for y, variant in enumerate(WORKLOADS):
        w = data[variant]
        c = w["candidate"]
        left = 0
        for scope, label, color in zip(SCOPES, labels, COLORS):
            n = c["recurrence_scope"][scope]
            pct = n / c["installs"] * 100
            ax.barh(y, pct, left=left, color=color, label=label if y == 0 else None, height=0.55)
            if pct >= 5:
                ax.text(left + pct / 2, y, f"{pct:.1f}%", ha="center", va="center", color="white" if scope != "first" else "#26343a")
            rows.append({"workload": variant, "scope": scope, "installs": n, "share": pct / 100})
            left += pct
        ax.text(101, y, f"n = {c['installs']:,}", va="center", fontsize=9)
    ax.set(yticks=range(3), yticklabels=[LABELS[v] for v in WORKLOADS], xlim=(0, 116), xlabel="Share of eligible installations (%)", title="Where Baseline compilation recurs")
    ax.set_xticks(range(0, 101, 20))
    ax.invert_yaxis()
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2, frameon=False, fontsize=9)
    fig.subplots_adjust(left=0.15, right=0.98, top=0.86)
    write_csv(output / "recurrence.csv", rows)
    summary = []
    for variant, w in data.items():
        c = w["candidate"]
        summary.append({"workload": variant, "record_id": w["record_id"], "installs": c["installs"], "keys": c["keys"], "repeats": c["installs"] - c["keys"], "linked_compiles": c["linked_compiles"], "linked_repeat_compiles": w["linked_repeat_compiles"], "compile_us": w["compile_us"], "repeat_compile_us": w["repeat_compile_us"]})
    write_csv(output / "compilation-work.csv", summary)
    finish(plt, fig, output, "recurrence", data, bottom=0.39)


def returns(plt, output, data):
    fig, axes = plt.subplots(3, 2, figsize=(11, 8.5))
    timeline_rows, gap_rows = [], []
    last_second = max(w["timeline"][-1]["second"] for w in data.values()) + 1
    peak_installs = max(b["first"] + b["repeat"] for w in data.values() for b in w["timeline"])
    gaps = [gap / 1e6 for w in data.values() for gap in w["recurrence_gaps_us"]]
    gap_limits = (min(gaps) * 0.8, max(max(gaps) * 1.2, 0.001)) if gaps else (0, 1)
    for (left, right), variant in zip(axes, WORKLOADS):
        w = data[variant]
        bins = w["timeline"]
        times = [b["second"] for b in bins]
        first = [b["first"] for b in bins]
        repeat = [b["repeat"] for b in bins]
        left.bar(times, first, color=COLORS[0], width=1, align="edge", label="First")
        left.bar(times, repeat, bottom=first, color=COLORS[1], width=1, align="edge", label="Repeat")
        left.set(title=LABELS[variant], ylabel="Installations / second", xlim=(0, last_second), ylim=(0, peak_installs * 1.22))
        left.text(0.98, 0.96, f"Origin: {w['timeline_origin_after_runner_us'] / 1e6:.2f} s after runner start", transform=left.transAxes, ha="right", va="top", fontsize=7)
        counts = Counter(w["recurrence_gaps_us"])
        cumulative = 0
        xs, ys = [], []
        for gap, count in sorted(counts.items()):
            cumulative += count
            xs.append(gap / 1e6)
            ys.append(cumulative / len(w["recurrence_gaps_us"]) * 100)
            gap_rows.append({"workload": variant, "gap_us": gap, "repeats": count, "cumulative_share": ys[-1] / 100})
        if xs:
            right.step([xs[0], *xs], [0, *ys], where="post", color=COLORS[1])
            # Symlog preserves exact zero gaps while displaying the positive tail logarithmically.
            right.set_xscale("symlog", linthresh=0.001)
        else:
            right.text(0.5, 0.5, "No repeated installations", ha="center", transform=right.transAxes)
        right.set(xlim=gap_limits, ylim=(0, 102), ylabel="Repeats at or below gap (%)", title=f"{len(w['recurrence_gaps_us']):,} recurrence intervals")
        right.grid(alpha=0.2)
        timeline_rows.extend({"workload": variant, **b} for b in bins)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[-1, 0].set_xlabel("Seconds since first eligible installation")
    axes[-1, 1].set_xlabel("Interval between matching installations (s; log above 1 ms)")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.94, hspace=0.55, wspace=0.3)
    write_csv(output / "timeline.csv", timeline_rows)
    write_csv(output / "recurrence-gaps.csv", gap_rows, ["workload", "gap_us", "repeats", "cumulative_share"])
    finish(plt, fig, output, "returns", data, bottom=0.20)


def multiplicity(plt, output, data):
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.8), sharey=True)
    rows = []
    maximum = max(row["installs_per_key"] for w in data.values() for row in w["multiplicity"])
    for ax, variant in zip(axes, WORKLOADS):
        w = data[variant]
        counts = w["multiplicity"]
        ax.bar([r["installs_per_key"] for r in counts], [100 * r["keys"] / w["candidate"]["keys"] for r in counts], color=COLORS[1])
        ax.set(title=LABELS[variant], xlabel="Installations per candidate key", xlim=(0, maximum + 1), ylim=(0, 100))
        ax.set_xticks(sorted({1, 5, 10, 20, maximum}))
        ax.text(0.97, 0.96, f"{w['candidate']['keys']:,} keys", transform=ax.transAxes, ha="right", va="top", fontsize=9)
        ax.grid(axis="y", alpha=0.2)
        rows.extend({"workload": variant, **r, "share": r["keys"] / w["candidate"]["keys"]} for r in counts)
    axes[0].set_ylabel("Share of distinct candidate keys (%)")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.86, wspace=0.15)
    write_csv(output / "multiplicity.csv", rows)
    finish(plt, fig, output, "multiplicity", data, bottom=0.29)


def source_label(filename):
    if filename.startswith("blob:"):
        return filename
    parts = urlsplit(filename)
    if parts.hostname in ("127.0.0.1", "localhost"):
        return parts.path
    return filename


def sources(plt, output, data):
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    all_rows, display_rows = [], []
    for ax, variant in zip(axes, WORKLOADS):
        w = data[variant]
        rows = [dict(r) for r in w["sources"][:5]]
        rest = w["sources"][5:]
        if rest:
            other = {key: sum(r[key] for r in rest) for key in ("keys", "installs", "repeats", "repeat_share", "compile_us", "repeat_compile_us")}
            other.update(filename=f"Other sources ({len(rest)})", repeat_compile_share=sum(r["repeat_compile_share"] for r in rest) if w["repeat_compile_us"] else None)
            rows.append(other)
        cells = []
        for row in rows:
            label = source_label(row["filename"])
            label = "\n".join(textwrap.wrap(label, 84, break_long_words=True, break_on_hyphens=False))
            cells.append([label, f"{row['keys']:,}", f"{row['installs']:,}", f"{row['repeats']:,}", f"{100 * row['repeat_share']:.1f}%", "—" if row["repeat_compile_share"] is None else f"{100 * row['repeat_compile_share']:.1f}%"])
            display_rows.append({"workload": variant, **row})
        ax.axis("off")
        ax.set_title(LABELS[variant], loc="left", pad=10)
        table = ax.table(cellText=cells, colLabels=["Source filename", "Keys", "Installs", "Repeats", "Repeat share", "Work share"], colWidths=[0.57, 0.075, 0.085, 0.085, 0.095, 0.09], cellLoc="right", bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor("#d9dfe2")
            cell.set_linewidth(0.4)
            if col == 0:
                cell.set_text_props(ha="left")
            if row == 0:
                cell.set_facecolor("#e6eeec")
                cell.set_text_props(weight="bold")
        all_rows.extend({"workload": variant, **r} for r in w["sources"])
    fig.subplots_adjust(left=0.03, right=0.97, top=0.94, hspace=0.36)
    write_csv(output / "sources.csv", all_rows)
    write_csv(output / "sources-displayed.csv", display_rows)
    finish(plt, fig, output, "sources", data, bottom=0.17)


def main(name):
    plt = plotting()
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    data = load_measurements()
    renderers = {"recurrence": recurrence, "returns": returns, "sources": sources, "multiplicity": multiplicity}
    renderers[name](plt, output, data)
    metadata = {
        "schema_version": 1, "artifact": name, "caption": CAPTIONS[name], "methodology": METHOD,
        "recordings": {v: {k: w[k] for k in ("record_id", "manifest", "firefox_revisions", "candidate", "recording")} for v, w in data.items()},
    }
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
