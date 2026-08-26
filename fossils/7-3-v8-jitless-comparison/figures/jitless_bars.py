#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Speedometer 3 and JetStream 3 headroom recovered from each engine's default.

Each workload occupies two horizontal bars stacked vertically:

    [V8 --jitless               ]                    | 100%  (green)
    [ interp \\\\\\  |  AmberMonkey #########]       | 100%  (amber)

The SpiderMonkey bar is a single amber bar composed of two segments so both
the interpreter-only baseline and AmberMonkey's headroom over default appear
in one row. This lets one small figure carry both S3 and JS3 comparisons
without doubling the plotted area over the earlier three-bar version.
"""

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
from fossil_figures import load_stdin

PROJECT_DIR = Path(os.environ.get("FOSSIL_PROJECT_DIR", Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from figure_style import (  # noqa: E402
    FONT_SIZES,
    apply_amber_style,
    figure_size,
    load_configurations,
)

from common import (
    load_sm_jetstream,
    load_v8,
    run_scores,
    save_png_and_pdf,
    summarize,
    summarize_column,
    v8_columns,
    validate_sm,
)


SM_DEFAULT = "default"
SM_INTERP = "interp-only"
SM_AM = "aot-corpus"
V8_DEFAULT = "v8-default"
V8_JITLESS = "v8-jitless"
CONFIGS = load_configurations()

# Per-segment styling — amber base for SM, green for V8.
SM_AMBER = CONFIGS[SM_AM]["color"]      # AmberMonkey red
V8_GREEN = CONFIGS[V8_JITLESS]["color"]
# Two-colour palette: green for V8, amber for the SM family. Three textures
# carry the configuration: crosshatch for V8, backslashes for SM interpreter,
# forward slashes for the AmberMonkey increment. Both SM segments share one
# alpha so only the hatch — not shading — distinguishes interp from AM. Alpha
# stays low (~0.3) so the hatch strokes read cleanly through the fill; some
# PDF viewers wash out dense hatches above ~0.4 alpha.
SM_ALPHA = 0.30
V8_ALPHA = 0.35
HATCH_INTERP = "\\\\"
HATCH_AM = "////"
HATCH_V8 = "xxx"


def sm_stack(sm_default: float, sm_interp: float, sm_am: float, sm_err_interp: float, sm_am_err: float):
    """Return (interp_ratio, am_ratio, interp_err, am_err) all as fractions of default."""
    if not sm_default:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        sm_interp / sm_default,
        sm_am / sm_default,
        sm_err_interp / sm_default,
        sm_am_err / sm_default,
    )


def v8_row(v8_default: float, v8_jitless: float, v8_jitless_stdev: float):
    if not v8_default or not v8_jitless:
        return (0.0, 0.0)
    return (v8_jitless / v8_default, v8_jitless_stdev / v8_default)


apply_amber_style("single")
plt.rcParams["hatch.linewidth"] = 1.6

data = load_stdin()
validate_sm(data, (SM_INTERP, SM_AM, SM_DEFAULT))
v8 = load_v8()

# --- Speedometer 3 --------------------------------------------------------
sp3_sm = {v: summarize(run_scores(data.columns[v]), 0.0) for v in (SM_INTERP, SM_AM, SM_DEFAULT)}
sp3_v8_cols = v8_columns(v8, "speedometer3")
sp3_v8 = {slug: summarize_column(sp3_v8_cols[slug]) for slug in (V8_DEFAULT, V8_JITLESS)}

sp3_interp_ratio, sp3_am_ratio, sp3_interp_err, sp3_am_err = sm_stack(
    sp3_sm[SM_DEFAULT][0], sp3_sm[SM_INTERP][0], sp3_sm[SM_AM][0],
    sp3_sm[SM_INTERP][1], sp3_sm[SM_AM][1],
)
sp3_v8_ratio, sp3_v8_err = v8_row(sp3_v8[V8_DEFAULT][0], sp3_v8[V8_JITLESS][0], sp3_v8[V8_JITLESS][1])

# --- JetStream 3 (may be TODO) -------------------------------------------
js3_sm_samples = load_sm_jetstream()
js3_sm_default = summarize(js3_sm_samples.get(SM_DEFAULT, []), 0.0)[0]
js3_sm_interp_mean, js3_sm_interp_stdev, _ = summarize(js3_sm_samples.get(SM_INTERP, []), 0.0)
js3_sm_am_mean, js3_sm_am_stdev, _ = summarize(js3_sm_samples.get(SM_AM, []), 0.0)

js3_v8_cols = v8_columns(v8, "jetstream3")
js3_v8 = {slug: summarize_column(js3_v8_cols[slug]) for slug in (V8_DEFAULT, V8_JITLESS)}

js3_interp_ratio, js3_am_ratio, js3_interp_err, js3_am_err = sm_stack(
    js3_sm_default, js3_sm_interp_mean, js3_sm_am_mean,
    js3_sm_interp_stdev, js3_sm_am_stdev,
)
js3_v8_ratio, js3_v8_err = v8_row(js3_v8[V8_DEFAULT][0], js3_v8[V8_JITLESS][0], js3_v8[V8_JITLESS][1])

# --- Layout ---------------------------------------------------------------
# Bar order, top-to-bottom (matplotlib y grows upward):
#   sp3_v8, sp3_sm, [gap], js3_v8, js3_sm
BAR_HEIGHT = 0.44
INNER_GAP = 0.02   # V8 and SM touch within a workload group
GROUP_GAP = 0.55
TOP_PAD = 0.30
BOTTOM_PAD = 0.30

y_js3_sm = 0.0
y_js3_v8 = y_js3_sm + BAR_HEIGHT + INNER_GAP
y_sp3_sm = y_js3_v8 + BAR_HEIGHT + GROUP_GAP
y_sp3_v8 = y_sp3_sm + BAR_HEIGHT + INNER_GAP
top_y = y_sp3_v8 + BAR_HEIGHT

def _center(bottom):
    return bottom + BAR_HEIGHT / 2

# The two workloads' bars are drawn independently so JS3 can degrade to a
# TODO placeholder without breaking the SP3 rendering.
fig, ax = plt.subplots(figsize=figure_size("single", 1.90))

def draw_v8(y_bottom, ratio, err):
    if ratio <= 0:
        ax.text(0.01, _center(y_bottom), "TODO — record V8 --jitless",
                ha="left", va="center", fontsize=FONT_SIZES["annotation"],
                style="italic", color="#666")
        return
    ax.barh(
        _center(y_bottom), ratio, height=BAR_HEIGHT,
        color=to_rgba(V8_GREEN, V8_ALPHA), edgecolor=V8_GREEN, linewidth=0.9,
        hatch=HATCH_V8,
        xerr=err, error_kw={"ecolor": "#333", "elinewidth": 0.8, "capsize": 2.0},
    )
    ax.text(
        ratio + err + 0.012, _center(y_bottom), f"{ratio * 100:.1f}%",
        ha="left", va="center", fontsize=FONT_SIZES["annotation"],
    )


def draw_sm_stack(y_bottom, interp_ratio, am_ratio, interp_err, am_err):
    if am_ratio <= 0:
        ax.text(0.01, _center(y_bottom), "TODO — bury 7-2-ambermonkey-perf-jetstream",
                ha="left", va="center", fontsize=FONT_SIZES["annotation"],
                style="italic", color="#666")
        return
    # Backslash segment: 0 → interp_ratio (the interpreter-only fraction).
    ax.barh(
        _center(y_bottom), interp_ratio, height=BAR_HEIGHT, left=0,
        color=to_rgba(SM_AMBER, SM_ALPHA), edgecolor=SM_AMBER, linewidth=0.9,
        hatch=HATCH_INTERP,
    )
    # Forward-slash segment: interp_ratio → am_ratio (AmberMonkey's headroom).
    increment = max(0.0, am_ratio - interp_ratio)
    ax.barh(
        _center(y_bottom), increment, height=BAR_HEIGHT, left=interp_ratio,
        color=to_rgba(SM_AMBER, SM_ALPHA), edgecolor=SM_AMBER, linewidth=0.9,
        hatch=HATCH_AM,
        xerr=am_err, error_kw={"ecolor": "#333", "elinewidth": 0.8, "capsize": 2.0},
    )
    # Interp % annotation inside the backslash segment (or just outside if
    # the segment is too narrow to hold the label).
    interp_label = f"{interp_ratio * 100:.1f}%"
    if interp_ratio >= 0.18:
        ax.text(interp_ratio - 0.008, _center(y_bottom), interp_label,
                ha="right", va="center", fontsize=FONT_SIZES["annotation"],
                color="#222")
    else:
        ax.text(interp_ratio + 0.008, _center(y_bottom), interp_label,
                ha="left", va="center", fontsize=FONT_SIZES["annotation"],
                color="#222")
    # AM total annotation at the right end of the whole bar.
    ax.text(
        am_ratio + am_err + 0.012, _center(y_bottom), f"{am_ratio * 100:.1f}%",
        ha="left", va="center", fontsize=FONT_SIZES["annotation"],
        fontweight="bold",
    )


draw_v8(y_sp3_v8, sp3_v8_ratio, sp3_v8_err)
draw_sm_stack(y_sp3_sm, sp3_interp_ratio, sp3_am_ratio, sp3_interp_err, sp3_am_err)
draw_v8(y_js3_v8, js3_v8_ratio, js3_v8_err)
draw_sm_stack(y_js3_sm, js3_interp_ratio, js3_am_ratio, js3_interp_err, js3_am_err)

ax.axvline(1.0, color="black", linewidth=0.8, linestyle="--", zorder=1)

# Workload group labels sit on the y-axis in the vertical middle of the
# corresponding pair of bars.
sp3_center = (y_sp3_sm + y_sp3_v8 + BAR_HEIGHT) / 2
js3_center = (y_js3_sm + y_js3_v8 + BAR_HEIGHT) / 2
ax.set_yticks([js3_center, sp3_center])
ax.set_yticklabels(["JS3", "SP3"], fontsize=FONT_SIZES["tick"])
ax.tick_params(axis="y", length=0, pad=4)

ax.set_ylim(-BOTTOM_PAD, top_y + TOP_PAD)

x_max = 1.12
ax.set_xlim(0.0, x_max)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
ax.set_xlabel("Score as % of engine's default")
ax.grid(axis="x", visible=True, linestyle=":", color="#BBBBBB", linewidth=0.6)
ax.set_axisbelow(True)

# Legend uses proxy patches so it reflects the segment styling exactly.
legend_handles = [
    Patch(facecolor=to_rgba(V8_GREEN, V8_ALPHA), edgecolor=V8_GREEN,
          hatch=HATCH_V8, label="V8 --jitless"),
    Patch(facecolor=to_rgba(SM_AMBER, SM_ALPHA), edgecolor=SM_AMBER,
          hatch=HATCH_INTERP, label="SM Interpreter only"),
    Patch(facecolor=to_rgba(SM_AMBER, SM_ALPHA), edgecolor=SM_AMBER,
          hatch=HATCH_AM, label="SM AmberMonkey"),
]
ax.legend(
    handles=legend_handles,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.02),
    ncol=3,
    frameon=False,
    handlelength=1.4,
    handleheight=0.9,
    handletextpad=0.4,
    columnspacing=1.0,
    borderpad=0.0,
    fontsize=FONT_SIZES["legend"],
)

fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.83)
save_png_and_pdf(fig, sys.argv[1])
