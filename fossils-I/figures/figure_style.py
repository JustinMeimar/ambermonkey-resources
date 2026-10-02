"""AmberMonkey's single source of truth for publication figures.

Figures must be generated at their final paper width.  A double-column PDF
placed in one column scales its fonts down with the image, even if its nominal
Matplotlib font sizes look correct.  These helpers keep physical typography
constant across both column widths and match the paper's Times-compatible font.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import matplotlib as mpl
from matplotlib.colors import to_hex, to_rgb


BASE_STYLE: dict[str, object] = {
    "figure.dpi": 150,
    "pdf.fonttype": 42,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "text.usetex": False,
    "errorbar.capsize": 3,
}

COLUMN_WIDTHS = {
    "single": 3.20,
    "double": 7.00,
}

FONT_SCALE = 0.80
FONT_SIZES = {
    "base": 10.0 * FONT_SCALE,
    "title": 11.0 * FONT_SCALE,
    "label": 10.0 * FONT_SCALE,
    "tick": 9.0 * FONT_SCALE,
    "legend": 9.0 * FONT_SCALE,
    "annotation": 8.0 * FONT_SCALE,
    "note": 7.0 * FONT_SCALE,
}

# Palette constants used for non-variant marks (whiskers, panel accents, etc.).
# All per-configuration colors live in configurations.toml; access
# them via load_configurations() instead of these constants.
AMBER_BLUE = "#2166AC"
AMBER_RED = "#B2182B"
AMBER_RED_MID = "#D6604D"
AMBER_PURPLE = "#762A83"
AMBER_ORANGE = "#E08214"
AMBER_GREY = "#7A7A7A"

# Shared grouped-bar treatment. Adjacent variants touch; Geo Mean groups are
# wider and use the same quiet background band in every applicable figure.
BAR_GROUP_WIDTH = 0.90
GEOMEAN_GROUP_WIDTH = 1.10
GEOMEAN_GROUP_GAP = 1.0 - BAR_GROUP_WIDTH
BAR_EDGE_WIDTH = 0.65
GEOMEAN_SHADE = "#F3F3F3"


def darken_color(color: str, factor: float = 0.70) -> str:
    """Return a darker, fully opaque outline color for a bar fill."""
    return to_hex(tuple(channel * factor for channel in to_rgb(color)))


def shade_geomean(ax, center: float) -> None:
    """Draw the shared Geo Mean summary band behind a grouped bar chart."""
    half_width = GEOMEAN_GROUP_WIDTH / 2
    ax.axvspan(
        center - half_width,
        center + half_width,
        color=GEOMEAN_SHADE,
        zorder=0,
    )


def load_configurations(registry_path):
    with registry_path.open("rb") as source:
        return tomllib.load(source)


def apply_amber_style(column: str) -> None:
    """Apply paper-matched typography at a declared publication width."""
    if column not in COLUMN_WIDTHS:
        raise ValueError(f"unknown publication column {column!r}")

    mpl.rcParams.update(
        {
            **BASE_STYLE,
            "figure.figsize": (COLUMN_WIDTHS[column], 2.4 if column == "single" else 3.5),
            "font.family": ["TeX Gyre Termes", "STIXGeneral"],
            "font.serif": ["TeX Gyre Termes", "STIXGeneral"],
            "font.size": FONT_SIZES["base"],
            "axes.titlesize": FONT_SIZES["title"],
            "axes.labelsize": FONT_SIZES["label"],
            "xtick.labelsize": FONT_SIZES["tick"],
            "ytick.labelsize": FONT_SIZES["tick"],
            "legend.fontsize": FONT_SIZES["legend"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def figure_size(column: str, height: float) -> tuple[float, float]:
    """Return an explicit final-size figure rectangle in inches."""
    if column not in COLUMN_WIDTHS:
        raise ValueError(f"unknown publication column {column!r}")
    return COLUMN_WIDTHS[column], height


def save_at_declared_size(fig, output_path: str | Path) -> None:
    """Save without tight-bbox expansion, preserving the publication width."""
    with mpl.rc_context({"savefig.bbox": None}):
        fig.savefig(output_path)
