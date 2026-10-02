# Baseline cache recordings

Start a three-minute interactive recording:

```sh
fossil bury 0-1-baseline-cache-simulation --project ambermonkey-oopsla --variant manual
```

This opens the instrumented Firefox build in a temporary profile. Visit sites
normally. The browser closes after 180 seconds, or you can close its window to
finish early. The runner collects the Baseline traces into the Fossil recording.
The temporary profile is removed afterward.

To include the latest recordings in the HTML report, run from the AmberMonkey
directory:

```sh
fossil emit 0-1-baseline-cache-simulation --project ambermonkey-oopsla --artifact detail
```

The artifact script writes `detail.json` and `index.html` under
`oopsla-2027/artifacts/0-1-baseline-cache-simulation/detail/`. Open `index.html`
to view the dashboard. It uses the latest recording of each variant.

Variant scripts receive the variant name as their first argument. Analysis
scripts receive the variant and record directory as arguments and one observation
as JSON on stdin. Runner settings live in `record.py`; Fossil does not inject
project paths or expand constants.

The report's **Download patches** link saves an embedded mailbox that can be
applied with `git am baseline-cache-instrumentation.patch`. The report shows the
Firefox base revision. The patch in `patches/` is exported from the instrumentation
commit recorded in the original benchmark traces; `patches/series.json` records
its commit and base revision.
