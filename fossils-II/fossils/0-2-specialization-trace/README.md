# Ion specialization recurrence

This fossil asks whether independent executions compile the same functions with
recurring **recorded specialization projections**. It does not install cached Ion
code, change compilation thresholds, or measure a cache speedup. The adjacent
Baseline-cache simulation remains a separate experiment.

One iteration runs two fresh training executions and one fresh evaluation
execution. Training ranks variants by number of training runs, then compilation
frequency, then signature. Evaluation tests membership in the frozen top 1, 2
and 4 variants per function key. A variant may occur in only one training run;
the report separately counts variants and function keys seen in both.

## What is recorded

At Ion compilation, the patch records function identities, the CacheIR selected
by Warp for the root and inlinees, dependency types, backend/oracle/link times,
code and metadata sizes, link outcomes, and local bailout/invalidation counts.
It does not trace IC attachments, fallbacks, full pre-Warp IC histories, Baseline
installations, or script lifetimes. Script identities are initialized lazily at
compilation. Ordinary engine warmup thresholds remain in force.

The function key hashes source text, bytecode, source encoding and immutable
flags; filenames and source locations do not participate. This is an advisory
content key, not a proof of semantic identity. Missing source is an exclusion;
encoding differences can split equivalent functions and hash collisions remain
possible.

Two projections are reported:

- `root`: selected CacheIR bytes, type data, scalar stub fields and recorded
  native shape layouts at each root bytecode offset.
- `snapshot`: the root and an unordered multiset of inlinee projections, content
  keys and dependency types. It also requires source for every inlinee.

Process-local pointer bits are erased. Symbols, prototypes, objects, shape-list
contents, constants behind pointers, inline call topology and optimizer guards
are not resolved. Non-CacheIR Warp snapshots and polymorphic type-data
specializations are not compared. Equal projections can therefore conceal incompatible native
code. Different projections show divergent compiler inputs, but do not prove a
more general cached variant would be unusable. Local bailouts are counts only;
they are not failures of a hypothetical transferred artifact.

The unit is a **successful local Ion compilation**, not an invocation or a
Baseline installation. Reports retain explicit denominators, missing-source and
no-selected-root exclusions, unlinked requests, variant growth, opaque field
counts, and compilation work associated with recurring projections. Backend
times are instrumented work weights; summed median code sizes are storage
estimates, excluding binding costs. There is no lifetime survival or
first-conflict metric. This sampling also says nothing about functions that
never reach Ion. Broader inputs and a real rebinding/guard-validation experiment
are needed before assessing safe cross-site reuse.

## Why the previous Speedometer run failed

In bundle `fcae11e02eb3405181873c0ac5021cff`, both training harnesses completed;
train-b then failed during JSON extraction. At line 360 of
`trace-child.11128.child-2.moz_log`, PID 11232's record occurs inside PID 11229's
record. Forked children shared a log file despite `%PID` naming. This was
interprocess record corruption, not a benchmark early exit.

Train-a generated 4,205,469,636 raw bytes. IC events alone occupied
3,545,236,611 bytes (84%); full profiles occupied another 256,438,785 bytes (6%).
Those event streams have been removed. This predicts a large reduction in trace
volume, but runtime overhead still needs measurement with the rebuilt browser.

Version 2 emits hex-encoded 512-byte JSON fragments in short `SPCACHE2` log
lines, identified by PID, process-start timestamp, event sequence and fragment
index/count. A process-local mutex serializes the writes across compiler
threads. **Use synchronous append logging** and retain every child log.
Extraction reassembles interleaved records and rejects duplicate, malformed,
legacy and incomplete records with file/line diagnostics where available.
It never repairs or skips corruption. Real browser validation is still required.

## Build and validate

From `/home/justin/spidermonkey`, rebuild using the existing browser mozconfig,
Nix environment and sccache configuration:

```sh
bash ambermonkey/fossils-II/fossils/0-2-specialization-trace/run-browser build
python3 -m unittest discover \
  -s ambermonkey/fossils-II/fossils/0-2-specialization-trace -p 'test_*.py'
```

The recorder checks that libxul contains the v2 framing marker before launching
a workload. It never rebuilds automatically. The launcher sources the single
cached `.direnv/flake-profile-*.rc`; `SPECIALIZATION_ENV_FILE` overrides it.
`FIREFOX_ROOT` defaults to `/home/justin/spidermonkey/firefox`.

First validate one traced run. Compare it with an untraced fresh run to assess
recording overhead; a single pair is diagnostic, not a performance claim:

```sh
cd /home/justin/spidermonkey/ambermonkey/fossils-II/fossils/0-2-specialization-trace
python3 capture.py speedometer3 --run probe --output /tmp/ion-recurrence-check
python3 capture.py speedometer3 --run untraced --no-trace --output /tmp/ion-recurrence-check
```

Check `summary.json`, `harness.log`, trace bytes and Raptor scores. Trace extraction
must complete without corruption. The harness uses CPU 2, headless mode, one
browser cycle and one page cycle for Speedometer/JetStream (two for tp6).
JetStream uses `tag=js&iterationCount=3&worstCaseCount=1`. Keep host settings and
benchmark revisions consistent. Then collect the independent three-run bundle:

```sh
fossil bury 0-2-specialization-trace --project ambermonkey-oopsla --variant speedometer3
```

`jetstream3` and `tp6` are also supported. tp6 historically took roughly
36 minutes per execution. `capture.py --dry-run` prints the planned launch.
Existing recording directories are never overwritten.

Raw traces, frozen Python tools, source diff, new instrumentation files, build
metadata and reports stay under
`$FIREFOX_ROOT/artifacts/specialization-browser/fossil-runs/<uuid>/`.
Archive the entire bundle. The binary/libxul/mozinfo hash must agree across all
three recordings, and analysis rejects overlapping process recordings.
Source snapshots describe the checkout; they do not prove those sources were
built. Frozen scripts mean edits take effect on the next invocation.

To repeat analysis of a completed v2 bundle:

```sh
python3 analyze.py --directory /path/to/bundle/speedometer3 > report.json
```

The v1 traces and reports remain historical artifacts and are intentionally
incompatible with this narrower v2 experiment. No successful browser build or
new workload measurement is claimed by the Python checks.
