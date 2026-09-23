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
python3 fossils-II/0-1-baseline-cache-simulation/render_dashboard.py \
  oopsla-2027/artifacts/0-1-baseline-cache-simulation-detail.json \
  oopsla-2027/artifacts/0-1-baseline-cache-simulation.html
```

The report's **Download patches** link saves an embedded mailbox that can be
applied with `git am baseline-cache-instrumentation.patch`. The report shows the
Firefox base revision. The patch in `patches/` is exported from the instrumentation
commit recorded in the original benchmark traces; `patches/series.json` records
its commit and base revision.
