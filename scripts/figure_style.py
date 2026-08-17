"""AmberMonkey's single source of truth for publication figures.

Figures must be generated at their final paper width.  A double-column PDF
placed in one column scales its fonts down with the image, even if its nominal
Matplotlib font sizes look correct.  These helpers keep physical typography
constant across both column widths and match the paper's Times-compatible font.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import matplotlib as mpl

from fossil_figures import apply_style


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

# Canonical deep endpoints from RdBu_r, also used by the 3-3 inter-workload
# coverage figure. The `default` / `aot-corpus` / etc. mappings below reuse
# these plus one PuOr orange for the AOT-with-full-tiering variant.
AMBER_BLUE = "#2166AC"
AMBER_RED = "#B2182B"
AMBER_PURPLE = "#762A83"
AMBER_ORANGE = "#E08214"
AMBER_GREY = "#7A7A7A"


def load_variant_colors():
    """Return {variant_name: hex_color} from the project's project.toml.

    Falls back to hardcoded defaults if the file or the individual keys are
    missing so a figure script cannot silently render with wrong colors —
    if a variant is unknown, its lookup raises KeyError at draw time.
    """
    project_toml = _find_project_toml()
    values = {}
    if project_toml is not None:
        try:
            data = tomllib.loads(project_toml.read_text())
            values = data.get("constants", {})
        except (OSError, tomllib.TOMLDecodeError):
            values = {}

    # Variant name -> project.toml key. Keep in sync with fossil variants
    # in 7-3-ambermonkey-perf and 7-11-sp3-memory.
    mapping = {
        "interp-only":    "VARIANT_COLOR_INTERP_ONLY",
        "aot-corpus":     "VARIANT_COLOR_AOT_CORPUS",
        "aot":            "VARIANT_COLOR_AOT",
        "default-no-ion": "VARIANT_COLOR_DEFAULT_NO_ION",
        "default":        "VARIANT_COLOR_DEFAULT",
    }
    defaults = {
        "interp-only":    AMBER_GREY,
        "aot-corpus":     AMBER_RED,
        "aot":            AMBER_ORANGE,
        "default-no-ion": AMBER_BLUE,
        "default":        AMBER_PURPLE,
    }
    return {v: values.get(key, defaults[v]) for v, key in mapping.items()}


def _find_project_toml():
    """Locate the ambermonkey project.toml under $FOSSIL_HOME (or ~/.fossil)."""
    home = Path(os.environ.get("FOSSIL_HOME", str(Path.home() / ".fossil")))
    candidate = home / "projects" / "ambermonkey" / "project.toml"
    return candidate if candidate.exists() else None


def apply_amber_style(column: str) -> None:
    """Apply paper-matched typography at a declared publication width."""
    if column not in COLUMN_WIDTHS:
        raise ValueError(f"unknown publication column {column!r}")

    apply_style(column=column)
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["TeX Gyre Termes"],
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
