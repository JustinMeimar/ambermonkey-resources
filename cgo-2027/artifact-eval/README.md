# AmberMonkey artifact smoke runs

Use the packaged image from `cgo-2027`:

```sh
mkdir -p artifact-results
docker run --rm --init --shm-size=2g \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke --suite
```

This runs the verified ordinary paths sequentially: **one selected variant per
experiment, one observation, 180-second command deadlines**. It continues after
an experiment fails and exits nonzero if any failed. This is a readiness check,
not a full reproduction of the paper's statistics. No engines are built.

```sh
# Inspect the exact selection without running anything.
docker run --rm ambermonkey-artifact-eval:smoke --suite --list
# Run only one suite entry.
docker run --rm --init --shm-size=2g \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke --suite --only 7-1-corpus-coverage
# Select an experiment/variant directly.
docker run --rm --init --shm-size=2g \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke \
  7-2-oracle-corpus --variant speedometer3-aot-only -n 1 --timeout 180
# Emit from saved records, without another benchmark run.
docker run --rm \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke \
  7-2-oracle-corpus --variant speedometer3-aot-only \
  --artifact speedometer3 --emit-only --timeout 30
```

Results persist under the mounted directory:

- `smoke-*.json`: suite status and each experiment's duration/outcome.
- `logs/*.json` and `logs/*.log`: individual command status and complete output.
- `records/`: Fossil observations and captured launch arguments.
- `artifacts/`: emitted tables/figures.
- `corpus/`: raw corpus artifacts produced by corpus construction.

A timeout terminates the subprocess group and reports `timed_out`. Failed or
partial observations are not reported as successful analyses. `--dry-run`
previews commands, and suite reports say `previewed`. `-n 1` retains the
experiment's normal internal benchmark cycles. Cross-variant artifacts can
require additional records; this runner intentionally selects one variant.

The image includes the engines, current Fossil, uv, perf and their native runtime
libraries. It requires no host `/nix/store`, source checkout, or executable mounts.
Internet access may still be needed for pinned Raptor workload/replay downloads.
Static tables, binary size and Octane have passed with `--network none`.

## Indirection counters

This optional path requires `CAP_PERFMON`; the ordinary suite does not request it.

```sh
docker run --rm --init --cap-add PERFMON \
  --mount "type=bind,src=$PWD/artifact-results,dst=/results" \
  ambermonkey-artifact-eval:smoke \
  7-5-indirection-overhead --variant am-rit -n 1 --timeout 180
```

Each of the three existing indirection binaries is now in a separate checksummed
archive with its embedded image. They are explicitly marked **candidate** because
their source revisions still need verification. The `am-rit` candidate passed
all ten microbenchmarks and counter analysis; the other variants were not run.

## Local development and image packaging

`bash artifact-eval/docker-run.sh ...` overlays the current source and host tools
on the cached base image. It supports the same arguments, including `--suite`.
It requires local `fossil`, `uv`, the archives and Docker access; indirection also
requires local `perf`. This route mounts Nix libraries read-only when present.

`bash artifact-eval/package-image.sh` assembles a new standalone local image from
these existing assets. It verifies/extracts archive caches, installs prebuilt
figure wheels from `uv.lock`, copies current scripts and native tool dependencies,
and prepares the Talos environment. It does not compile Firefox, V8, or Fossil.
The base image is pinned by digest in the script. The image contains
`/workspace/artifact-eval-current/bundle-manifest.json` with native tool hashes.

The historical Dockerfile bootstraps old source and Fossil revisions and is not
the supported packaging route. Use `package-image.sh` for this no-compilation
workflow. Nothing has been pushed to a registry.

See `../ARTIFACT_EVAL_PROGRESS.md` for the per-experiment evidence and blockers.
