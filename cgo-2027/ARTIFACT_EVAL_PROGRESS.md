# Artifact evaluation progress

**13/14 experiments have a successful Docker smoke path.** A checked box means
one selected variant (or named static artifact) completed execution and required
analysis/emission. It does **not** mean all variants or paper-quality statistics.
Every benchmark smoke used `-n 1` with a timeout; no engine/compiler builds or
all-variant runs were performed.

## Kick off the verified suite

From this directory:

```sh
mkdir -p artifact-results
docker run --rm --init --shm-size=2g \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke --suite
```

The suite runs 12 ordinary entries sequentially and records per-experiment status.
Use `--suite --list` to inspect the plan or `--suite --only EXPERIMENT` to select
one. Hardware-counter indirection is separate and requires `--cap-add PERFMON`.
See `artifact-eval/README.md` for that command and artifact-only rendering.

Local image:
`sha256:190a9dfff907398810d56fb5932d599d25abfb01dc90d4f82186bf31a3dd8d84`
(tag `ambermonkey-artifact-eval:smoke`, approximately 11.7 GB).
It needs no host source, executable, or `/nix/store` mounts. Internet can still
be needed for pinned Raptor workload/replay downloads. Nothing was published to
a registry.

## Experiments

- [x] `0-0-static-tables`: both runtime-dependencies and execution-configurations tables emitted. Verified offline in the standalone image.
- [ ] `3-3-cross-workload-reuse`: **blocked on an instrumented browser package**. Amazon replay worked, but reduction found no content instrumentation JSONL. See the source revision below. Excluded from the suite; direct invocation now explains the prerequisite immediately.
- [x] `6-1-corpus-construction`: Amazon recording passed; an initial run recorded 885 baseline functions and 975 IC bodies. A repeat verified persistent raw files under `corpus/amazon`. Full corpus composition needs the other sites and self-hosted recording.
- [x] `7-1-corpus-coverage`: Speedometer execution, coverage analysis and baseline-function table passed. Seven processes produced dumps; the initial smoke observed 3,750 baseline-function AOT hits and 1,239,182 IC AOT hits. Other workloads remain untested.
- [x] `7-2-ambermonkey-perf-s3`: `default` executed and analyzed successfully in about 94–97 seconds. AM execution variants and the full performance ladder remain untested.
- [x] `7-2-ambermonkey-perf-octane`: `default` executed and analyzed successfully in about 28 seconds, including offline standalone verification. Full ladder needs a matched AM shell/image package.
- [x] `7-2-oracle-corpus`: `speedometer3-aot-only` executed, analyzed and emitted its table in about 98–100 seconds. Launch-policy validation passed. Matched default comparison remains untested; its ratio is null in the single-policy table.
- [x] `7-3-v8-jitless-comparison`: `speedometer-v8-jitless` executed and analyzed in about 90 seconds. Uses existing non-PGO Chromium 155.0.8042.0 and checksummed matching ChromeDriver. Octane still needs d8 and matching AM shell packages; other comparison variants remain untested.
- [x] `7-4-artifact-installation-cost`: `default-no-ion` executed, produced content-process AOT_TIMING records, analyzed and emitted the attachment table. Packaged Talos works without a configured Firefox build. Comparison fields remain null without AOT samples.
- [x] `7-4-artifact-installation-startup`: `default-no-ion` executed and analyzed all six expected JetStream startup workloads in about 40 seconds. Other configurations remain untested.
- [x] `7-5-indirection-overhead`: existing `am-rit` candidate passed all ten microbenchmarks and counter analysis in about 13 seconds. Also verified offline from the final standalone image, using `CAP_PERFMON`. The other two candidate variants remain untested; source revisions still need verification.
- [x] `7-5-indirection-e2e-s3`: `default-no-ion` executed, analyzed and emitted its perf table. The paper requires an oracle corpus, so the mapping is `am-browser-release-oracle-sp3`; that corrected mapping was verified offline in 98.2 seconds. AOT variant remains untested.
- [x] `7-6-cross-process-memory-sharing`: `default` executed, analyzed and emitted the aggregate table. Five content processes had nonzero executable RSS/PSS and anonymous executable memory. Docker headless launch and packaged-path validation were fixed. AOT-sharing comparisons remain untested.
- [x] `7-6-binary-size`: packaged-browser table emitted for default and AM tp6, including offline standalone verification. Full libxul/image decomposition still needs matched corpus/AOTImage.inc metadata and usable symbols; package totals are not build-tree totals.

## Container and harness work

- [x] Verify and extract the four original archives into separate directories, retaining each binary's embedded image.
- [x] Add separately checksummed Chromium and exact-version ChromeDriver archives.
- [x] Package each existing indirection binary/image in its own archive, explicitly marked candidate.
- [x] Use current Fossil `bury`, `analyze`, and `emit` APIs with current fossils-I definitions.
- [x] Add packaged-engine/path overrides while retaining local-build defaults.
- [x] Reuse cached Raptor dependencies via a harness-only mozconfig.
- [x] Run Talos directly against a packaged browser without build-tree configuration.
- [x] Install figure dependencies from uv.lock using prebuilt wheels (`--no-build`).
- [x] Preserve records, artifacts, raw corpora, command logs and status JSON outside the container.
- [x] Package current tools, runtime libraries, definitions and extracted engines into a standalone local image.
- [ ] Verify exact source revisions/corpus identities for all engine packages before a final reviewer release. Browser application.ini/platform.ini contain BuildIDs but no source revision.
- [ ] Publish/export the reviewer artifact when ready; the current image is local only.

## Verification evidence

`artifact-image-results/` contains the standalone image checks:

- `smoke-1792972323071017254.json`: **3/3 passed**, network disabled; static tables, browser size and Octane (28.8 seconds total).
- `smoke-1792972404890120365.json`: **9/9 passed**, network enabled; remaining ordinary entries (640.5 seconds total).
- `records/7-5-indirection-e2e-s3/20261026_000607_361_default-no-ion_/`: successful corrected oracle-package run, network disabled, plus analysis and table emission.
- `logs/1792973226949837155.json` and `logs/1792973239594038488.json`: final-image indirection execution and analysis both passed, network disabled and only CAP_PERFMON added.

Earlier development records are in `artifact-smoke-results/`. Both directories
are ignored by Git. Command status/log pairs live under `logs/`; suite status
files use `smoke-*.json`. The runner reports `passed`, `failed`, or `timed_out`,
and dry-run suites report `previewed`.

Additional checks verified timeout termination, nonzero-exit reporting, source
syntax, and checklist coverage. Memory analysis accepted a real packaged-browser
record and rejected a wrong browser path and a forbidden AOT flag.

## Fundamental remaining prerequisite

The cross-workload fossil requires the JSInstr lifecycle/IC/demand/baseline
interface. Neither pinned browser package nor any existing release/debug browser
build contains JS_INSTR_MODE/JS_INSTR_DIR. The current Firefox checkout also lacks
the interface. AOT coverage dumps are different measurements and cannot replace it.

The matching source exists locally on `justin/ambermonkey-preliminary-evals`, at:

```text
4af61d93c9d73f8d9bda10a0085b8e5cb96cdbc4 (2026-08-26)
```

That branch's `js/src/jit/Instr.cpp` contains the required environment variables,
source_class fields and baseline-entries-retire events. An existing package from
this instrumentation-enabled source, or a new build from the appropriate revision,
is needed. No build was started under the no-build constraint.

Further full-reproduction prerequisites remain: matched AM shell/image packages
(the default shell exposes no AOT options), d8 for Octane, indirection source
provenance, and all-variant/statistical runs intentionally deferred during this pass.
