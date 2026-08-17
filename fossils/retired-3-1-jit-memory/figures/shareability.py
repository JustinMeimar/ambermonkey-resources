#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Peak-snapshot JIT residency per artifact class, split into currently_shared / achievable_shared / unique bands."""

import json
import sys

import matplotlib.pyplot as plt
import numpy as np

from fossil_figures import apply_style

MB = 1024.0 * 1024.0

CODE = {
    "baseline-script:guest-chrome": "App",
    "trampoline":                   "Tr",
    "baseline-ic":                  "IC",
    "baseline-interpreter":         "BI",
    "baseline-script:self-hosted":  "SH",
    "shared-ic":                    "FB",
    "regexp":                       "Re",
}

C_CURRENT = "#2E86AB"
C_ACHIEVE = "#F6AE2D"
C_UNIQUE  = "#C73E1D"


def die(msg):
    print(f"shareability figure: FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def pick_variant(data):
    if len(data) == 1:
        return next(iter(data.values()))
    for k in ("awsy-tp6-stock", "awsy-tp6-stock-quick"):
        if k in data:
            return data[k]
    return next(iter(data.values()))


def scalar(v):
    if isinstance(v, dict) and "mean" in v:
        return float(v["mean"])
    return float(v)


def main():
    out_path = sys.argv[1]
    v = pick_variant(json.load(sys.stdin))

    rows = []
    for a in v["artifacts"]:
        if a["name"] not in CODE:
            die(f"unknown artifact class {a['name']!r}: add a short "
                f"code to CODE")
        total = scalar(a["total"]) / MB
        cur = scalar(a["currently_shared"]) / MB
        ach = scalar(a["achievable_shared"]) / MB
        unq = scalar(a["unique"]) / MB
        rows.append({
            "name": a["name"], "total": total,
            "currently_shared": cur, "achievable_shared": ach, "unique": unq,
        })
    rows.sort(key=lambda r: -r["total"])

    apply_style(column="single")
    plt.rcParams["figure.figsize"] = (3.4, 2.7)
    fig, ax = plt.subplots()
    y = np.arange(len(rows))
    h = 0.65
    xmax = max(r["total"] for r in rows)

    for i, r in enumerate(rows):
        x0 = 0
        ax.barh(y[i], r["currently_shared"], left=x0, height=h,
                color=C_CURRENT, edgecolor="white", linewidth=0.3)
        x0 += r["currently_shared"]
        ax.barh(y[i], r["achievable_shared"], left=x0, height=h,
                color=C_ACHIEVE, edgecolor="white", linewidth=0.3)
        x0 += r["achievable_shared"]
        ax.barh(y[i], r["unique"], left=x0, height=h,
                color=C_UNIQUE, edgecolor="white", linewidth=0.3)
        shareable = r["currently_shared"] + r["achievable_shared"]
        pct = 100 * shareable / r["total"] if r["total"] else 0
        ax.text(r["total"] + xmax * 0.015, y[i],
                f"{r['total']:.2f} ({pct:.0f}%)",
                va="center", fontsize=7, color="#222")

    ax.set_yticks(y)
    ax.set_yticklabels([CODE[r["name"]] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("Browser-wide resident bytes at peak (MB)")
    ax.set_axisbelow(True)
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, xmax * 1.40)

    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=C_CURRENT, label="shares today"),
        Patch(facecolor=C_ACHIEVE, label="shares under AOT"),
        Patch(facecolor=C_UNIQUE,  label="irreducible"),
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=3,
              frameon=False, fontsize=7)

    fig.tight_layout()
    fig.savefig(out_path)


if __name__ == "__main__":
    main()
