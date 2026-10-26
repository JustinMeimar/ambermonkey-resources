# Ion template candidate experiment

The benchmark variants `speedometer3` and `jetstream3`, and the ten live NavBench
route variants, capture schema 5 Ion compilation lifecycles using the release
browser from `justin/in-memory-cache-experiments-v157`. Each Fossil observation
runs the selected workload twice, sequentially, in independent browser launches:
training, then evaluation. There is no actual Ion cache enabled.

Run from the Firefox development environment (`direnv`), after building with
`just build build-browser-release`:

```sh
fossil bury 0-5-ion-templates --project ambermonkey-oopsla --variant speedometer3 --iterations 1
fossil bury 0-5-ion-templates --project ambermonkey-oopsla --variant jetstream3 --iterations 1
fossil analyze 0-5-ion-templates:speedometer3 --project ambermonkey-oopsla --last 1
fossil analyze 0-5-ion-templates:jetstream3 --project ambermonkey-oopsla --last 1
```

Omitting `--variant` runs all twelve. Each iteration creates its own training/evaluation
pair; donors never leak between observations or benchmarks. `FIREFOX_ROOT` can
select another checkout, provided its release browser and analyzer match.
To inspect the commands without running a benchmark:

```sh
python3 fossils/0-5-ion-templates/record.py speedometer3 --dry-run
python3 fossils/0-5-ion-templates/record.py jetstream3 --dry-run
python3 fossils/0-5-ion-templates/record.py workspace-shuffle --dry-run
```

## Workloads and records

The shared `common/browser_workloads.py` launcher supplies one browser cycle and
one page cycle per phase. Speedometer uses the harness defaults. JetStream uses
the existing JS-only configuration, `tag=js&iterationCount=3&worstCaseCount=1`;
it is not the full default JetStream suite. Both run headless with normal
helper-thread Ion compilation. The harness's default startup delay is retained.

Raw traces, harness logs, commands, exit codes, source revision/diff, libxul hash,
and analyzer hash remain under
`$FIREFOX_ROOT/artifacts/ion-templates/<timestamp>-<variant>/`. The analyzer and
runner are archived there for provenance. `manifest.json` is written before
capture, and `report.json` only after both phases succeed. Fossil stores the
report in observation stdout. A failed phase or missing valid installed guest
compilations fails the observation; partial logs remain available.

The active replay implementation is imported directly from
`$FIREFOX_ROOT/js/src/jit/ion_recurrence.py`; this experiment does not maintain a
second implementation. The Fossil analyzer re-reads the raw traces named by the
report's `directory` and replays them with the current analyzer, so it ignores the
report's own metrics and works on any schema-5 record whose traces remain on disk.
System-realm compilations are excluded; guest and self-hosted compilations are
replayed separately. Compilations without a valid key are excluded from both
pools and counted in `invalid_key_requests`; on route runs these are a handful of
parent-process scripts whose source text was not retained.

## NavBench routes

The route variants (`workspace-shuffle`, `media-pinball`, `wiki-rabbit-hole`,
`cake-quest`, `compiler-coffee`, `debugging-detour`, `headline-hop`,
`comparison-cart`, `weekend-wayfinder`, `paper-trail`) run the visit sequences in
`../common/navbench_routes.toml` live, signed out, through Browsertime's
interactive driver. The launcher, profile and visit validation are shared with
`0-3-navbench-ion-recurrence` via `../common/navbench_routes.py`. Each phase runs
the route's two passes in one cold browser session, with a fresh profile built
from Raptor's base profile directories. Route runs are not headless.

Revisits inside a route (`docs-a` twice in `workspace-shuffle`, and every page
again in the second pass) appear in the `runtime` and `session` pools.
`training` measures what the training session offers the evaluation session.
Live content changes between phases, so unlike the benchmarks, the two runs do not
execute identical code. A phase fails if any visit is missing or reports an error;
inspect `browsertime/` in the phase directory for consent screens or challenges.

## Interpretation

Each evaluation compilation is replayed against three donor pools:

- `runtime`: installed earlier in the same runtime.
- `session`: installed earlier anywhere in the evaluation session, with the
  analyzer's 1 ms cross-process clock margin.
- `training`: every installation from the training session, all available at
  evaluation startup.

Per pool, guest compilations report:

- `*_hit_fraction`: share of requests whose exact `(function, template)` key had
  a donor.
- `*_hit_cpu_fraction`: share of backend CPU spent on those requests.
- `*_identity_only_fraction`: share of requests whose function had a donor, but
  only under different templates. The remainder are functions with no donor.

The other guest metrics are `requests`, `backend_cpu_ms`, `top1_template_coverage`
and `top2_template_coverage` (share of requests served if each function kept only
its one or two most frequent templates), and `fingerprint_overhead` (key
computation elapsed time over backend CPU). Self-hosted compilations report
`self_hosted_requests` plus hit and identity-only fractions for the `session`
and `training` pools.

Backend CPU is helper-thread work, not page time or benchmark speedup.

The key preserves recorded specialization inputs modulo pointer bindings; it
does not establish exact semantic type-profile equivalence or safe machine-code
reuse. The model assumes unlimited capacity, no lookup/binding costs, and the
observed request schedule. Instrumentation and synchronous logging add overhead.
These runs measure recurrence candidates and associated compilation work, not
an actual template implementation's performance.

Lower-tier execution time before Ion is not yet instrumented. Startup template
availability therefore does not yet yield an estimate of warmup savings. The
`training` pool measures compilation candidates available from a prior run,
not time saved by bypassing the JIT warmup lifecycle.

Schema 4 adds explicit `key_failures` breakdowns, including request counts,
outcomes and backend CPU/elapsed cost. Source failures distinguish the root,
guest inlinees and self-hosted inlinees, and identify absent source text, empty
extent, extent outside source bounds, or a null result from `substringChars`.
Other reasons are snapshot not described, reference-map allocation failure, and
zero fingerprint. Combined reasons form one category to prevent double-counting.
`substring_chars_failed` names the precise failing API; its return value cannot
distinguish allocation from decompression failure. The analyzer rejects older
reports that did not record these reasons. Use `--last 1` for the new capture
rather than combining it with the previous schema-3 observations.

Schema 5 identifies self-hosted functions by the engine's script-transcoding
build ID and their retained source start/end positions. Stencil instantiation
preserves these positions, including nested functions. Source text is not
required for these engine-owned functions. Immutable flags, inline structure,
bytecode and specialization inputs remain part of the fingerprints. Guest
functions still require source text. A missing build ID is a recorded failure,
not permission to match functions across builds. Use the latest observation:
schema-4 and schema-5 keys are not interchangeable.
