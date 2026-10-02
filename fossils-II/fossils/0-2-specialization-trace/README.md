# Ion feedback recurrence

This experiment asks whether recurring functions reach Ion compilation with
recurring type feedback, and how Warp's choices add or remove variation.
AmberMonkey supplies the motivation for sharing compiled artifacts. Native code
identity, native addresses, and native code size are not recurrence criteria.
The instrumentation leaves normal compilation thresholds and optimization
choices in place. There is one current schema, with no compatibility support.

## Observations

Every compilation attempt records an entry profile before its root Warp oracle
starts selecting or folding ICs. Each attempted inlinee has its own profile,
captured before that inlinee's oracle runs, with a unique context, parent, and
call-site offset. Inlinee profiles are therefore observations at recursive
oracle entry, not a simultaneous snapshot of the entire potential call graph.
Failed inline attempts remain in the raw data but are excluded from the accepted
inlining tree. A root attempt remains an observation even if compilation fails.

Each IC site records its ordered CacheIR chain, field descriptors, cumulative
entered counts, fallback count, mode, attachment-failure state, trial-inlining
state, and folding hint. Warp's decisions are recorded separately: selected
CacheIR, inlining, ordered polymorphic type data, cold/invalid-fuse bailouts, and
reasons for generic IC execution. Completed script snapshots also record all
snapshot kinds and offsets, including non-CacheIR snapshots. Missing decisions
at sites Warp does not consult are distinct from generic decisions.

There is no continuous attachment/fallback history. A profile is captured only
when an oracle begins. Synchronous framed logging prevents records from forked
processes corrupting each other. Extraction rejects incomplete, duplicated, or
malformed frames; it never repairs or skips corruption. Use `sync,append`.

## Comparison layers

| Layer | Compared | Deliberately separate |
| --- | --- | --- |
| `entry` | Ordered chains, CacheIR, type data, normalized fields, IC mode and attachment-failure state | Exact counters and optimization hints |
| `active` | The same descriptors for cases with nonzero successes, plus fallback activity | Exact frequencies |
| `consumed` | Root Warp decisions, selected CacheIR, ordered polymorphic types | Inlinee contents and compilation history |
| `context` | Consumed feedback through the accepted inlining tree, call sites, history flags, OSR offset, IC hints, snapshot kinds, dependency kinds | Unrecorded snapshot/dependency payloads |

A stub's success count is its entered count minus its successor's entered count,
with the same unsigned arithmetic as Warp. Raw counts remain available to study
frequency effects, but count differences alone do not split entry profiles.
Empty profiles and cold sites are retained.

Guest function keys combine source text, bytecode, encoding and immutable
flags, without filenames. They are advisory content identities, not semantic
proofs. Self-hosted keys use bytecode, source coordinates and immutable flags
within the exact engine build. All compared recordings must use that build.
Unresolved guest identities are reported and excluded from key-based matches.

Scalar field values and linear-string contents participate in comparisons.
Shapes contribute recorded property layouts. Interpreted function/script fields
contribute content keys when available. Native addresses do not participate.
Shape identity/prototypes, closure environments, native callee identities,
folded shape-list contents, and other pointer-backed values remain unresolved.
The report counts those occurrences and identifies matched entry profiles with
no unresolved fields. Descriptor matches with unresolved fields are coarse
profile recurrence, not fully characterized equality. Non-CacheIR snapshot and
dependency payload gaps are reported separately. `context` is not a complete
compiler-input identity, and differing contexts do not prove reuse impossible.

## Analysis

The default burial collects two fresh training executions and one held-out
execution of a workload. It reports each layer's recurrence **conditional on
function recurrence**, as well as the denominator over all eligible attempts.
There is a separate view restricted to successful compilations in both training
and evaluation. Compiler work is associated with observations; instrumented
elapsed durations are not saved wall-clock time.

The report includes:

- Per-function variant counts and growth in supplied recording order.
- Repetition from earlier recordings versus repetition first seen within the
  current recording. This does not infer page-load boundaries.
- New consumed feedback despite recurring entry feedback, changed entry
  feedback despite recurring consumed feedback, and new optimization contexts
  despite recurring consumed feedback.
- Entry-profile mismatch distances and categories, against the nearest observed
  training profile by differing-site count. Categories can overlap; they are
  descriptive, not causal optimization ablations.
- Top-1/2/4 profile concentration, ranked using training recording frequency,
  then compilation frequency, then signature. This is not a cache policy.
- Explicit missing-identity, unresolved-field, incomplete-oracle and successful
  compilation populations. No code-size-based reuse inference is made.

The full report contains per-function details and bounded divergence examples.
Fossil's metrics adapter omits provenance, detailed examples, recording names,
and undefined percentages while retaining their denominators.

Repeated benchmark inputs measure repeatability. Cross-workload analysis accepts
independently recorded directories, in the intended learning order:

```sh
python3 analyze.py --training /path/to/earlier/run \
  --training /path/to/another/run --evaluation /path/to/held-out/run > report.json
```

This permits shared-library recurrence across workloads without requiring equal
workload names. It does not manufacture a browsing timeline from benchmark
iterations. Navigation boundaries, changed-input cohorts, actual bounded-cache
policies, and targeted optimization ablations are follow-on experiments after
validating these observations. Do not disable optimizations merely to reduce
the number of variants.

## Build and validate

From `/home/justin/spidermonkey`:

```sh
bash ambermonkey/fossils-II/fossils/0-2-specialization-trace/run-browser build
```

The recorder checks libxul for the feedback framing marker and refuses to run
without it. It never builds automatically. The launcher uses the provisioned
Nix environment, browser mozconfig and sccache configuration.
`SPECIALIZATION_ENV_FILE` and `FIREFOX_ROOT` override their default locations.

Start with one traced recording and validate it before a full burial:

```sh
cd /home/justin/spidermonkey/ambermonkey/fossils-II/fossils/0-2-specialization-trace
python3 capture.py speedometer3 --run probe --output /tmp/ion-feedback-check
python3 capture.py speedometer3 --run untraced --no-trace --output /tmp/ion-feedback-check
```

Capture validates the feedback graph after extracting the logs. Check unresolved
coverage in the full report, trace bytes, harness time and
Raptor scores. Hashing and synchronous output perturb execution; a traced versus
untraced pair is an overhead diagnostic, not evidence of a cache speedup. The
harness pins to CPU 2 and retains normal warmup thresholds. Speedometer's internal
iterations are not independent page-load observations. Browser execution still
needs validation after rebuilding; C++ syntax checks do not
replace it.

Then collect the full bundle:

```sh
fossil bury 0-2-specialization-trace --project ambermonkey-oopsla --variant speedometer3
fossil analyze 0-2-specialization-trace:speedometer3 \
  --project ambermonkey-oopsla --analysis specialization --last 1
```

`jetstream3` and `tp6` are also available. `capture.py --dry-run` prints the launch
without running it. Existing output directories are never overwritten.

Raw traces, scripts, source changes, build identity, metadata, and the full
report stay under
`$FIREFOX_ROOT/artifacts/specialization-browser/fossil-runs/<uuid>/`.
Frozen scripts document what an experiment ran. Source snapshots do not prove
that those sources were built. Archive the entire bundle.

```sh
python3 analyze.py --directory /path/to/bundle/speedometer3 > report.json
```
