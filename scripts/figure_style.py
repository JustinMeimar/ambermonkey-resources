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

# Palette constants used for non-variant marks (whiskers, panel accents, etc.).
# All per-configuration colors live in fossils/configurations.toml; access
# them via load_configurations() instead of these constants.
AMBER_BLUE = "#2166AC"
AMBER_RED = "#B2182B"
AMBER_RED_MID = "#D6604D"
AMBER_PURPLE = "#762A83"
AMBER_ORANGE = "#E08214"
AMBER_GREY = "#7A7A7A"


def load_configurations():
    """Load the execution-configuration registry.

    Returns dict[slug] -> {"long", "short", "prose", "color", "order"}.
    Reads from $FOSSIL_PROJECT_DIR/configurations.toml (the fossil-home copy)
    or falls back to the repo-local path. Missing entries raise KeyError at
    lookup time so a figure cannot silently render an unknown variant.
    """
    registry_path = _find_registry()
    if registry_path is None:
        raise FileNotFoundError(
            "configurations.toml not found; set FOSSIL_PROJECT_DIR or run "
            "from a checkout of ambermonkey"
        )
    with registry_path.open("rb") as f:
        return tomllib.load(f)


def load_variant_colors():
    """Deprecated: use load_configurations()[slug]['color']."""
    return {slug: cfg["color"] for slug, cfg in load_configurations().items()}


def _find_registry():
    project_dir = os.environ.get("FOSSIL_PROJECT_DIR")
    if project_dir:
        candidate = Path(project_dir) / "configurations.toml"
        if candidate.exists():
            return candidate
    home = Path(os.environ.get("FOSSIL_HOME", str(Path.home() / ".fossil")))
    candidate = home / "projects" / "ambermonkey" / "configurations.toml"
    if candidate.exists():
        return candidate
    repo = Path(__file__).resolve().parents[1] / "fossils" / "configurations.toml"
    return repo if repo.exists() else None


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
