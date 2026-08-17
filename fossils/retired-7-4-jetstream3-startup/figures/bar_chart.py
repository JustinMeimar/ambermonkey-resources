#!/home/justin/tools/fossil/figures/.venv/bin/python
"""JetStream 3 overall vs first-iteration scores per variant, normalized to runtime-lazy."""

import sys

from fossil_figures import apply_style, load_stdin, comparison_bar

apply_style(column="double")
data = load_stdin()

baseline = "runtime-lazy"
if baseline not in data.column_names:
    baseline = data.column_names[0]

fig = comparison_bar(
    data,
    metrics=["overall_score", "startup_score"],
    normalize_to=baseline,
    ylabel=f"JS3 score, relative to {baseline} (higher is better)",
    title="JetStream 3: overall vs first-iteration score",
)
fig.savefig(sys.argv[1])
