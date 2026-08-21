#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Two-panel heatmap of IC-body overlap.

Panel (a) is the symmetric static intersection; panel (b) is the directional
dynamic intersection with A on rows (source workload) and B on columns
(evaluated workload). Renders at roughly two-thirds of the double-column
width so the paper can pair it with a native-typeset formula block.
"""

import sys
from decimal import ROUND_DOWN, Decimal

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from fossil_figures import apply_style, load_stdin


apply_style(column="double")
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
# Match the paper: Times-family serif so panel titles and tick labels
# typeset in the same style as the surrounding prose.
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = [
    "Times New Roman", "TeX Gyre Termes", "STIX Two Text", "DejaVu Serif",
]
plt.rcParams["mathtext.fontset"] = "stix"
data = load_stdin()
tp6_subset = (
    "amazon",
    "bing-search",
    "buzzfeed",
    "cnn",
    "ebay",
    "espn",
    "expedia",
    "facebook",
)
missing = [name for name in tp6_subset if name not in data.columns]
if missing:
    print(
        "artifact-overlap: missing selected TP6 workloads: " + ", ".join(missing),
        file=sys.stderr,
    )
    sys.exit(1)

columns = list(tp6_subset)
n = len(columns)


def tag(metric, key):
    if not metric.children or key not in metric.children:
        return ""
    return (metric.children[key].tag or "").strip()


def decode_set(metric, key):
    encoded = tag(metric, key)
    return set(encoded.split(",")) if encoded else set()


def decode_counter(metric, key):
    encoded = tag(metric, key)
    values = {}
    if encoded:
        for entry in encoded.split(";"):
            identity, count = entry.rsplit("=", 1)
            values[identity] = int(count)
    return values


def floor_2(value):
    return format(
        Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_DOWN),
        ".2f",
    )


def text_color(cmap, norm, value):
    red, green, blue, _ = cmap(norm(value))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "white" if luminance < 0.48 else "black"


def static_matrix(sets):
    matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            union = sets[i] | sets[j]
            matrix[i, j] = len(sets[i] & sets[j]) / len(union) if union else 0.0
    return matrix


def dynamic_matrix(source_sets, target_frequencies):
    matrix = np.zeros((n, n))
    for i, source in enumerate(source_sets):
        for j, target in enumerate(target_frequencies):
            total = sum(target.values())
            if total:
                matrix[i, j] = sum(
                    count for identity, count in target.items() if identity in source
                ) / total
    return matrix


metrics = [data.columns[column] for column in columns]
ic_sets = [decode_set(metric, "ic_hashes") for metric in metrics]
ic_frequencies = [decode_counter(metric, "ic_freqs") for metric in metrics]

for column, ic_set, ic_freqs in zip(columns, ic_sets, ic_frequencies):
    if not ic_set or not ic_freqs:
        print(f"artifact-overlap: incomplete metrics for {column}", file=sys.stderr)
        sys.exit(1)

ic_static = static_matrix(ic_sets)
ic_dynamic = dynamic_matrix(ic_sets, ic_frequencies)

# The data is bimodal — panel (a) sits near 0.55-0.68 and panel (b) near
# 0.89-1.00 — with no observations in between. A logit-shaped norm on the
# tightened [0.55, 1.0] window puts colour resolution at both ends where
# the data lives and lets the empty middle band compress. Truncating the
# palest sliver of YlOrRd also lifts panel (a) off the near-cream low end.
_base_cmap = mpl.colormaps["YlOrRd"]
cmap = mpl.colors.LinearSegmentedColormap.from_list(
    "YlOrRd_trunc", _base_cmap(np.linspace(0.18, 1.0, 256))
)
scale_ticks = np.array([0.55, 0.65, 0.75, 0.85, 0.90, 0.95, 1.00])
_norm_epsilon = 0.04


def _norm_forward(values):
    values = np.asarray(values, dtype=float)
    t = np.clip((values - 0.55) / (1.0 - 0.55), _norm_epsilon, 1.0 - _norm_epsilon)
    logits = np.log(t / (1.0 - t))
    lower = np.log(_norm_epsilon / (1.0 - _norm_epsilon))
    upper = -lower
    return (logits - lower) / (upper - lower)


def _norm_inverse(positions):
    positions = np.asarray(positions, dtype=float)
    lower = np.log(_norm_epsilon / (1.0 - _norm_epsilon))
    upper = -lower
    logits = lower + positions * (upper - lower)
    t = 1.0 / (1.0 + np.exp(-logits))
    return 0.55 + t * (1.0 - 0.55)


norm = mpl.colors.FuncNorm(
    (_norm_forward, _norm_inverse),
    vmin=0.55,
    vmax=1.0,
)

display = [name.replace("google-", "g-") for name in columns]

fig = plt.figure(figsize=(5.9, 3.65))
# Colorbar in the rightmost thin gridspec column; the two heatmaps take
# the remainder. The paper places native-typeset formulas beside the PDF.
gs = fig.add_gridspec(
    1, 3, width_ratios=[1.0, 1.0, 0.05], wspace=0.45
)
ax_static = fig.add_subplot(gs[0, 0])
ax_dynamic = fig.add_subplot(gs[0, 1])
cax = fig.add_subplot(gs[0, 2])

heatmap_axes = (ax_static, ax_dynamic)
titles = (
    "(a) Static intersection $S(A, B)$",
    "(b) Dynamic intersection $D(A, B)$",
)
matrices = (ic_static, ic_dynamic)

for index, (axis, title, matrix) in enumerate(zip(heatmap_axes, titles, matrices)):
    axis.imshow(
        matrix, cmap=cmap, norm=norm, interpolation="nearest", aspect="equal"
    )
    axis.set_xticks(np.arange(-0.5, n, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, n, 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=0.6)
    axis.tick_params(which="minor", bottom=False, left=False)
    axis.grid(False, which="major")
    axis.set_title(title, fontsize=8.6, pad=5)
    axis.set_xlim(-0.5, n - 0.5)
    axis.set_ylim(n - 0.5, -0.5)
    axis.set_xticks(range(n))
    axis.set_xticklabels(
        display,
        rotation=55,
        rotation_mode="anchor",
        ha="right",
        va="top",
        fontsize=6.3,
    )
    axis.tick_params(axis="x", length=0, pad=1)
    axis.set_yticks(range(n))
    axis.set_yticklabels(display, fontsize=6.3)
    axis.tick_params(axis="y", length=0, pad=1)
    for spine in axis.spines.values():
        spine.set_visible(False)

    for i in range(n):
        for j in range(n):
            if i == j:
                value = 1.0
                axis.add_patch(
                    plt.Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        facecolor=cmap(norm(value)),
                        edgecolor="white",
                        linewidth=0.6,
                    )
                )
                color = text_color(cmap, norm, value)
                weight = "bold"
            else:
                value = matrix[i, j]
                color = text_color(cmap, norm, value)
                weight = "normal"
            axis.text(
                j,
                i,
                floor_2(value),
                ha="center",
                va="center",
                fontsize=5.6,
                fontweight=weight,
                color=color,
            )

ax_static.set_ylabel("Workload", fontsize=7.4, labelpad=3)
ax_dynamic.set_xlabel("Evaluated workload $B$", fontsize=7.4, labelpad=3)
# Panel (b)'s ylabel moves to the right so the left gutter between the
# two heatmaps can tighten to almost nothing.
ax_dynamic.set_ylabel("Source workload $A$", fontsize=7.4, labelpad=8)
ax_dynamic.yaxis.set_label_position("right")

fig.subplots_adjust(left=0.04, right=0.98, bottom=0.20, top=0.905)
# Colorbar is shorter than the axes box so its ends line up with the
# square matrix area rather than the tick labels and title.
_cax_pos = cax.get_position()
_shrink = 0.80
_new_h = _cax_pos.height * _shrink
cax.set_position([
    _cax_pos.x0,
    _cax_pos.y0 + (_cax_pos.height - _new_h) / 2,
    _cax_pos.width,
    _new_h,
])
colorbar = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
colorbar.set_ticks(scale_ticks)
colorbar.set_ticklabels([".55", ".65", ".75", ".85", ".9", ".95", "1"])
colorbar.ax.tick_params(labelsize=5.2, length=2)
colorbar.set_label("IC-body overlap", fontsize=6.6, labelpad=2)

fig.savefig(sys.argv[1], dpi=300)
