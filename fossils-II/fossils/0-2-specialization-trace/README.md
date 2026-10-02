# Specialization trace experiment

This adjacent fossil preserves `0-1-baseline-cache-simulation`. Each variant
records two independent training executions and one held-out execution with
both Baseline and specialization logging enabled. No eager-compilation hints
are applied. One Fossil iteration therefore launches three benchmark runs.

## Provision and run

Keep this directory alongside `fossils/common` in the project.
Run from a terminal with loopback networking, benchmark download access, a
provisioned Raptor/Browsertime environment and write access to the build's Mach
state. The restricted coding session cannot open the required loopback socket.

```sh
export FIREFOX_ROOT=/home/justin/spidermonkey/firefox
fossil bury 0-2-specialization-trace --project ambermonkey-oopsla --variant speedometer3
fossil bury 0-2-specialization-trace --project ambermonkey-oopsla --variant jetstream3
fossil bury 0-2-specialization-trace --project ambermonkey-oopsla --variant tp6
```

The launcher sources the single cached `../.direnv/flake-profile-*.rc` file.
Set `SPECIALIZATION_ENV_FILE` to override it. It uses the mozconfig recorded in
`build-browser-release/mozinfo.json` and never rebuilds. The browser must already
contain the instrumentation. Its executable, libxul and mozinfo bytes determine
the build identifier; the analyzer rejects recordings from different builds.

The run settings match the original experiment: CPU 2; one browser cycle;
one page cycle for Speedometer 3 and JetStream 3, two for tp6; JetStream uses
`tag=js&iterationCount=3&worstCaseCount=1`. Automated runs are headless. Keep the
host governor, boost, benchmark revisions and machine load consistent across
recordings; the harness logs retain the actual benchmark setup and scores.
The historical tp6 recording took roughly 36 minutes for one execution, so
budget substantially longer for its complete three-execution variant.

Raw logs, Raptor outputs, engine source diff, new instrumentation files,
mozconfig, build metadata, frozen analysis tools, manifests and detailed reports
remain under `$FIREFOX_ROOT/artifacts/specialization-browser/fossil-runs/<uuid>/`.
Archive that directory with the Fossil record. Fossil stdout stores the completed
aggregate report and the raw directory location, not the large trace files.
An interrupted/failed run keeps its files but does not emit a successful report.

The terminal shows recording 1/3, 2/3 and 3/3, live harness output, and a
15-second heartbeat with elapsed time and trace size. Complete output stays in
`harness.log`; long terminal lines are abbreviated. Failed harness runs stop
before trace extraction. To watch a recording launched with an older runner,
use `tail -f <recording-directory>/harness.log`. Running recordings use frozen
scripts, so source edits take effect on the next invocation.

Both cache fossils use `fossils/common/browser_workloads.py` for benchmark
arguments and manual-profile defaults, and `fossils/common/baseline_cache_trace.py`
for the Baseline log format. Specialization analysis remains specific to this
fossil. Each experiment snapshots this fossil and the shared directory, generating
`SHA256SUMS.json` for those exact files so later edits cannot change its analysis.

For manual recovery or a dry run:

```sh
python3 capture.py speedometer3 --run train-a --output /absolute/output --dry-run
python3 capture.py speedometer3 --run train-a --output /absolute/output
python3 capture.py speedometer3 --run train-b --output /absolute/output
python3 capture.py speedometer3 --run evaluation --output /absolute/output
python3 analyze.py --directory /absolute/output/speedometer3 > report.json
```

Existing recording directories are never overwritten by capture. Analysis may
be rerun and replaces derived manifests and transfer reports. `capture.py manual`
also supports fresh interactive 180-second recordings, but these are not part
of the automated Fossil variants.

## Decision metrics

The report separates guest, system and self-hosted code, excluding missing
source from content-identity analysis. For one, two and four variants per key:

* Coverage: recurring Ion keys, selected-profile keys, eligible evaluation
  lifetimes and Baseline installations at keys seen in training. Baseline joins
  report unmatched records explicitly rather than assuming complete coverage.
* Compatibility: first-ranked variant survival, any-variant survival, and
  survival with every selected site observed. Each percentage retains its
  numerator and denominator; a zero denominator produces null.
* Conflict timing: warmup counts at the first recorded contradiction of the
  first-ranked variant. Warmup includes calls and backedges and can reset.
* Work and space: recorded backend work associated with compatible projections,
  Ion code sizes, estimated storage from per-variant median code sizes, and
  Baseline code-plus-metadata sizes. These are different accounting measures;
  Ion binding/metadata costs are still unknown.
* Reuse obstacles: inlining, dependency types, opaque stub fields, local bailouts,
  invalidations, requests without successful links, and censored lifetimes.

Use the fixed first-variant result to assess a concrete training-only policy.
Any-variant survival is a hindsight estimate of the benefit of a better selector.
Low fully-observed survival or large variant/storage growth argues against a
simple optimized-code cache. High coverage and stable projections identify
candidates for a subsequent prepared-code or reduced-optimization experiment.

Neither agreement nor a lack of logged bailouts proves transferred code is safe:
the log does not validate optimizer guards, prototypes, constants or inlined
dependencies. Instrumented compilation times are work weights, not predicted
wall-time savings. Benchmark scores from these logged runs are not a speedup
measurement. This experiment supplies compatibility and opportunity evidence;
actual cache installation, rebinding and execution costs need a later treatment.

The two-training/one-evaluation design is an initial characterization. Repeating
the Fossil variant yields independent experiment bundles; different site inputs
and separately trained compiler configurations are necessary before generalizing
to cross-site reuse or making claims about warp-lite.
