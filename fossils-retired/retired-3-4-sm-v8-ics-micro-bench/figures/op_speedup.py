#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Per-operation loop-adjusted V8/SM speedup on the ic-microbench kernels.

Vertical bar chart authored at single-column width. Bars above the x-axis
(blue) are cases where SpiderMonkey Baseline with CacheIR completes an
operation faster than V8 Sparkplug; bars below (red) are cases where V8 is
faster. Y-axis is log2(V8_sparkplug / SM), so doubling and halving sit one
unit apart and the extreme `array_destructure` case stays visible without
dwarfing the arithmetic wins.
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.ticker import FuncFormatter
import numpy as np
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    AMBER_BLUE,
    AMBER_RED,
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    save_at_declared_size,
)


COLUMN = "seed"

# Short labels chosen to fit at single-column width with 17 kernels.
DISPLAY_NAMES = {
    "unary_negate_int32": "Int neg",
    "unary_bitnot_int32": "Int bit-not",
    "binary_add_int32": "Int add",
    "binary_string_int32_sub": "Str−int sub",
    "binary_bigint_add_sub": "BigInt ±",
    "compare_int32_false": "Int cmp",
    "compare_string_false": "Str cmp",
    "to_bool_string": "Str truthy",
    "typeof_eq_number": "typeof cmp",
    "call_monomorphic": "Mono call",
    "lambda_clone": "Func alloc",
    "new_object": "Obj alloc",
    "new_array": "Arr alloc",
    "array_destructure": "Array destr.",
    "spread_call": "Spread call",
    "iterator_close_missing_return": "Iter close",
    "to_property_key_compound": "Prop-key comp.",
}


def scalar_at(metric, *path):
    node = metric
    for key in path:
        if not node.children or key not in node.children:
            raise KeyError(f"missing {'.'.join(path)!r}")
        node = node.children[key]
    if node.scalar is None:
        raise ValueError(f"{'.'.join(path)!r} is not scalar")
    return node.scalar.mean


def case_order(metric):
    order_node = metric.children.get("case_order") if metric.children else None
    if order_node is None or order_node.tag is None:
        raise ValueError("analysis output missing case_order tag")
    return [name for name in order_node.tag.split(",") if name]


apply_amber_style("single")

data = load_stdin()
if COLUMN not in data.columns:
    raise SystemExit(f"missing '{COLUMN}' column; found {sorted(data.column_names)}")

seed = data.columns[COLUMN]
cases_metric = seed.children.get("cases") if seed.children else None
if cases_metric is None or not cases_metric.children:
    raise SystemExit("analysis output missing 'cases' map")

try:
    ordered_cases = case_order(seed)
except Exception:
    ordered_cases = sorted(
        cases_metric.children,
        key=lambda name: -scalar_at(cases_metric.children[name], "v8_over_sm"),
    )

ordered_cases = [c for c in ordered_cases if c in cases_metric.children]

log2_speedup = np.array([
    scalar_at(cases_metric.children[case], "log2_v8_over_sm")
    for case in ordered_cases
])
v8_over_sm = np.array([
    scalar_at(cases_metric.children[case], "v8_over_sm")
    for case in ordered_cases
])
labels = [DISPLAY_NAMES.get(c, c) for c in ordered_cases]

order = np.argsort(-log2_speedup)
log2_speedup = log2_speedup[order]
v8_over_sm = v8_over_sm[order]
labels = [labels[i] for i in order]

colors = [AMBER_BLUE if v >= 0 else AMBER_RED for v in log2_speedup]
face_colors = [to_rgba(c, 0.55) for c in colors]

x = np.arange(len(labels))
fig, ax = plt.subplots(figsize=figure_size("single", 2.55))

ax.bar(
    x,
    log2_speedup,
    color=face_colors,
    edgecolor=colors,
    linewidth=0.8,
    width=0.78,
)

ax.axhline(0.0, color="black", linewidth=0.7)
ax.grid(axis="y", linestyle=":", color="#BBBBBB", linewidth=0.5)
ax.set_axisbelow(True)

y_min_log = np.floor(min(log2_speedup.min(), -1.0))
y_max_log = np.ceil(max(log2_speedup.max(), 1.0))
ax.set_ylim(y_min_log - 0.35, y_max_log + 0.80)


def ratio_label(value, _pos):
    ratio = 2 ** value
    if value == 0:
        return "1×"
    if ratio >= 1:
        return f"{ratio:g}×"
    return f"1/{1.0 / ratio:g}×"


ax.yaxis.set_major_locator(plt.MultipleLocator(1.0))
ax.yaxis.set_major_formatter(FuncFormatter(ratio_label))
ax.set_ylabel("V8 / SM cost (loop-adjusted)")

# Only annotate the extreme bars: the strongest SM win, strongest V8 win,
# and the balanced pair around 1×. Everything else risks stacking on top of
# the neighbouring bar at single-column width.
annotate_idx = {0, 1, len(log2_speedup) - 1, len(log2_speedup) - 2}
for xi, log_v, ratio in zip(x, log2_speedup, v8_over_sm):
    if xi not in annotate_idx:
        continue
    text = f"{ratio:.2f}×"
    if log_v >= 0:
        ax.text(
            xi,
            log_v + 0.15,
            text,
            ha="center",
            va="bottom",
            fontsize=FONT_SIZES["annotation"],
            color=AMBER_BLUE,
        )
    else:
        ax.text(
            xi,
            log_v - 0.15,
            text,
            ha="center",
            va="top",
            fontsize=FONT_SIZES["annotation"],
            color=AMBER_RED,
        )

ax.set_xticks(x)
ax.set_xticklabels(
    labels,
    rotation=50,
    ha="right",
    rotation_mode="anchor",
    fontsize=FONT_SIZES["tick"],
)
ax.tick_params(axis="x", length=0, pad=2)
ax.set_xlim(-0.7, len(labels) - 0.3)

ax.text(
    0.005,
    0.985,
    "SM CacheIR faster",
    transform=ax.transAxes,
    ha="left",
    va="top",
    color=AMBER_BLUE,
    fontsize=FONT_SIZES["legend"],
)
ax.text(
    0.995,
    0.020,
    "V8 Sparkplug faster",
    transform=ax.transAxes,
    ha="right",
    va="bottom",
    color=AMBER_RED,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.18, right=0.995, bottom=0.28, top=0.97)
out = Path(sys.argv[1])
save_at_declared_size(fig, out)
save_at_declared_size(fig, out.with_suffix(".png"))
