# Baseline compilation measurements

Records compilation, installation, and discard events. The four artifacts measure
candidate-key recurrence without cache simulation. The directory name preserves
existing recording identities.

## Generate artifacts

From the AmberMonkey directory:

```sh
uv sync --project fossils-II
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact recurrence
```

Replace `recurrence` with any artifact below, or generate it in Fossil's web view.

| Artifact | Measurement |
| --- | --- |
| `recurrence` | First/repeated installations by runtime and process; CSV includes compilation work and matching coverage. |
| `returns` | First/repeated installations over time and the distribution of intervals between matching installations. |
| `sources` | Top five filenames plus the remainder, with keys, installs, repeats, and shares of repeats and compilation work; full source list in CSV. |
| `multiplicity` | Number of installations per candidate key. |

Outputs are PDF, CSV data, and `provenance.json` under
`oopsla-2027/artifacts/0-1-baseline-cache-simulation/<artifact>/`.

Generators select the latest record ID for each of SP3, JS3, and TP6 directly,
independently of `--last`, `--variant`, or web analysis selection. All three are
required; failed, incomplete, or multi-observation recordings fail generation
without falling back. Manual captures remain available for analysis.

## Interpretation

- Population: guest Baseline installations with a source fingerprint, one
  observation per workload. These figures do not estimate variation across runs.
- Identity: filename, source span and encoding, source/bytecode hashes, immutable
  flags, and debug instrumentation. Matching keys are not proven native-code
  equivalence. Scope compares the immediately preceding match's PID and runtime
  address; addresses can be reused.
- Timing: installation follows compilation and linking. Calls to installed code
  produce no event. Recurrence gaps are between installations, not execution or
  discard intervals. Recorded backend durations are instrumentation-affected work
  weights, not elapsed time saved; helper-thread work can overlap.
- Sources: grouped by exact filename, with display-only local-URL abbreviations.
  Source text was not recorded.
- Quality: malformed lines are excluded and counted on each PDF. The current
  benchmark recordings each have two. Counts describe valid recorded events.

`analyze_detail.py` links events and collects eligible installations;
`measurements.py` provides shared source aggregation and plot data;
`artifacts.py` renders the PDFs and exports data. Thin entry points connect these
to Fossil. Both `recurrence` and `detail` analyses remain available. Detailed
analysis retains provenance, compilation/size distributions, size variation,
and matched install-to-discard lifetimes. Lifetimes span all provenances and
only matched discards, so they are not a guest-code survival estimate.

## Record

```sh
fossil bury 0-1-baseline-cache-simulation --project ambermonkey-oopsla --variant manual
```

Opens instrumented Firefox with a temporary profile for 180 seconds; close the
window to finish early. `record.py` holds runner settings. Variant scripts receive
the variant name; analysis scripts receive variant and record directory, with
one observation as JSON on stdin.

`patches/` retains the instrumentation patch and its commit/base revisions.
Raw records and historical dashboard outputs are retained; the dashboard is no
longer configured.
