# Baseline compilation measurements

This fossil records compilation, installation, and discard events. Its artifacts
measure candidate-key recurrence; they do not simulate a cache or predict speedups.
The directory name is retained so existing recordings keep their identity.

## Artifacts

Install plotting dependencies once from the AmberMonkey directory:

```sh
uv sync --project fossils-II
```

Emit any artifact through Fossil (also available in the web view):

```sh
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact recurrence
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact returns
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact sources
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact multiplicity
```

- `recurrence`: first installation and recurrence scope across SP3, JS3, and TP6.
  Includes a CSV of observed compilation work and matching coverage.
- `returns`: first/repeated installations over time and empirical distributions
  of the wall-clock interval between consecutive matching installations.
- `sources`: top five source filenames per workload plus all remaining sources,
  with distinct keys, installations, repeats, and shares of repeats and repeated
  compilation work. The full source table is retained as CSV.
- `multiplicity`: distribution of the number of installations per candidate key.

Each directory under `oopsla-2027/artifacts/0-1-baseline-cache-simulation/`
contains a PDF, CSV data, and `provenance.json`. Captions state population
and interpretation; provenance retains record IDs, revisions, trace quality,
compilation matching coverage, and methodology.

Generators deliberately read the latest record directory for each benchmark,
ordered by Fossil record ID. They do not consume averaged Fossil analysis input,
so `--last` and `--variant` do not change this selection. All three benchmarks
must be present. A failed, incomplete, or multi-observation selected recording
fails generation rather than silently substituting an older recording. Each
artifact compares one observation per workload; it does not estimate variation
across runs. Manual captures remain available for analysis but are excluded from
these benchmark comparisons.

## Measurement definitions

`analyze_detail.py` links events and computes recurrence once. `measurements.py`
reduces those events into the data used by the four artifact renderers. Both
`recurrence` and `detail` Fossil analyses remain available without LRU replay.

The figure population is guest Baseline installations with a source fingerprint.
The candidate key includes filename, source span and encoding, source and
bytecode hashes, immutable flags, and debug instrumentation. It approximates
body identity, not proven native-code equivalence. Scope compares the most
recent prior matching installation's PID and runtime address. Addresses can be
reused; this is not a count of persistent script instances.

An installation follows compilation and linking. Executing already-installed
code produces no installation event. Recurrence gaps measure intervals between
installations, not idle time, execution intervals, or install-to-discard lifetime.
Recorded backend durations are work weights affected by instrumentation and
potential helper-thread overlap, not elapsed benchmark time saved. Source rows
group exact filenames; source text was not recorded. Abbreviating a local URL in
the displayed table does not change grouping or candidate identity.

Malformed lines are excluded by the recorder and their counts are displayed on
every artifact. The existing SP3, JS3, and TP6 recordings each have two such lines;
measurements describe valid recorded events and may omit events from those lines.

The detailed analysis also retains provenance summaries, compilation and size
distributions, matched install-to-discard lifetimes, and size variation within
candidate keys. Its lifetime summary spans all provenances and only matched
discards, so it is not a guest-code survival estimate.

## Recordings and instrumentation

Start a three-minute interactive recording:

```sh
fossil bury 0-1-baseline-cache-simulation --project ambermonkey-oopsla --variant manual
```

This opens the instrumented Firefox build in a temporary profile. Visit sites
normally. The browser closes after 180 seconds, or close its window to finish
early. The runner collects traces and removes the temporary profile afterward.

Variant scripts receive the variant name as their first argument. Analysis
scripts receive the variant and record directory as arguments and one observation
as JSON on stdin. Runner settings live in `record.py`.

`patches/0001-baseline-cache-trace.patch` preserves the instrumentation patch;
`patches/series.json` identifies its commit and Firefox base revision. Raw records
and previously generated dashboard files are retained, but the dashboard is no
longer a configured artifact.
