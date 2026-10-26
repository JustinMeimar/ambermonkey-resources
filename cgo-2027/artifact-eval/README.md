# AmberMonkey artifact (CGO 2027)

Reproduces the evaluation (Section 7) of the AmberMonkey paper using prebuilt
engines. Nothing is compiled except the small Fossil benchmark harness.

## Requirements

- x86-64 Linux with Docker, ~40 GB free disk, internet access (image build and
  Raptor page-load recordings).
- For `7-5-indirection-overhead`: hardware performance counters visible to
  containers (bare metal or a VM with a virtual PMU).

## Run

```sh
./reproduce.sh --list                            # show experiments, variants, repetitions
./reproduce.sh                                   # run everything (many hours)
./reproduce.sh --only 7-2-ambermonkey-perf-s3    # one experiment (repeatable)
./reproduce.sh --only 7-6-binary-size -n 1       # quick check with 1 repetition
./reproduce.sh --resume run-YYYYMMDD-HHMMSS      # continue a run; passed steps are skipped
```

The first call builds the `ambermonkey-artifact` image (about 30 minutes);
later calls reuse it. Each run writes to `results/run-<timestamp>/`:

- `artifacts/<experiment>/`: the paper's tables and figures
- `status.json`: pass/fail and duration for every step
- `logs/`: full output of every step
- `records/`: raw Fossil observations

A step fails if any repetition fails. If a variant fails, its experiment's
figures are not emitted.

## Experiments

| Experiment | Paper | Engines | n |
|---|---|---|---|
| 7-1-corpus-coverage | AOT corpus coverage on held-out workloads | AM browser (tp6) | 3 |
| 7-2-ambermonkey-perf-s3 | Speedometer 3 tier ladder | default + AM browser | 10 |
| 7-2-ambermonkey-perf-octane | Octane 2 tier ladder | AM jsshell (tp6) | 10 |
| 7-2-oracle-corpus | Speedometer 3 with oracle corpus | AM browser (oracle) | 10 |
| 7-3-v8-jitless-comparison | Retained performance vs V8 jitless | AM browsers, AM jsshell, Chromium | 10 |
| 7-4-artifact-installation-cost | Per-artifact installation cost (Talos) | AM browser | 10 |
| 7-4-artifact-installation-startup | JetStream 3 startup latency | AM browser | 30 |
| 7-5-indirection-overhead | Indirection microbenchmarks (perf counters) | 3 AM shells | 50 |
| 7-5-indirection-e2e-s3 | Indirection overhead on Speedometer 3 | AM browser (oracle) | 10 |
| 7-6-cross-process-memory-sharing | Content-process PSS/USS | default + AM browser | 3 |
| 7-6-binary-size | On-disk size of libxul, image, browser | default + AM browser | 1 |

Not included:

- 7-1 `octane2`: the packaged jsshell has no AOT coverage dump.
- 7-3 `octane-v8-*`: they need d8, which is not part of this artifact. Because
  the 7-3 figures require every variant, 7-3 produces per-variant analyses but
  not its combined figure.

## Contents

| File | Purpose |
|---|---|
| `reproduce.sh` | builds the image and runs `run.py` inside it |
| `run.py` | runs the plan with Fossil: bury, check, analyze, emit |
| `evaluation.json` | the plan: experiments, variants, repetitions, outputs |
| `releases.json` | checksums and layout of the prebuilt engines in `releases/` |
| `Dockerfile` | pinned Fossil, experiment definitions, Firefox harness, engines |
| `install_releases.py`, `prepare_raptor.py`, `run_talos.py` | image build/runtime helpers |

Engines are unpacked to `/opt/engines/<name>` in the image. Experiment
definitions live in `/workspace/fossils-I` (from `ambermonkey-resources`).
