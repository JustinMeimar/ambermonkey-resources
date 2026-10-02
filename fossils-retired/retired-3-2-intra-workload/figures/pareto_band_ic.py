#!/home/justin/tools/fossil/figures/.venv/bin/python
"""Ranked IC-body entry CDF band across the TP6 subset."""
import sys

from fossil_figures import FigureData, apply_style, load_stdin, ranked_cdf_band


TP6_SITES = (
    "amazon",
    "bing-search",
    "buzzfeed",
    "cnn",
    "ebay",
    "espn",
    "expedia",
    "facebook",
)

apply_style(column="single")
data = load_stdin()
missing = [site for site in TP6_SITES if site not in data.columns]
if missing:
    raise SystemExit(f"missing TP6 columns: {', '.join(missing)}")
data = FigureData(columns={site: data.columns[site] for site in TP6_SITES})
fig = ranked_cdf_band(
    data,
    metric="ranked_counts",
    xlabel="Attached IC bodies (ranked by entry count)",
    ylabel="Fraction of total stub entries",
    thresholds=[0.9],
    log_x=True,
)
fig.savefig(sys.argv[1])
