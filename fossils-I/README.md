# fossils

Benchmark experiments for AmberMonkey. Each subdirectory is one fossil — a
self-contained experiment with a `fossil.toml` declaring its variants,
analyses, figures, and tables.

## Layout

```
fossils-I/
  project.toml          project identity and artifact destination
  configurations.toml   display names and colors
  common/               launch settings, browser/shell helpers, Octane harness
  scripts/              shared parsers and figure utilities (../scripts)
  fossils/
    <N-M-slug>/
      fossil.toml       variants, analyses, and artifact scripts
      run.py            variant runner
      scripts/          experiment-local helpers
      analyses/         per-observation parsers
      figures/          plot and table emitters
      records/          fossil-managed observations
  retired/              unmigrated experiments
```

## Fossils

Numbering tracks the final ACM paper: 3-X = Section III (Structured ICs),
6-X = Section VI (Experimental Design and Corpus Construction), and 7-X =
Section VII (Evaluation). The cross-cutting hand-authored tables retain the
reserved 0-0 prefix. Retired fossils keep a `retired-<orig-N-M>-<slug>`
directory name so provenance stays legible.

### Active

| fossil                                      | topic                                        | final paper subsection                |
|---------------------------------------------|----------------------------------------------|---------------------------------------|
| `0-0-static-tables`                         | hand-authored taxonomy tables                | Tables 1 and 2 (cross-cutting)        |
| `3-3-cross-workload-reuse`                  | cross-workload reuse (tp6-Train/Test)        | 3.3 Cross-Workload Reuse              |
| `6-1-corpus-construction`                   | AOT corpus recorder over tp6 + self-hosted   | 6.1 Corpus Construction               |
| `7-1-corpus-coverage`                       | corpus coverage on held-out workloads        | 7.1 AOT Corpus Coverage               |
| `7-2-ambermonkey-perf-s3`                   | Speedometer 3 performance ladder             | 7.2 Restricted-Execution Performance |
| `7-2-ambermonkey-perf-octane`               | Octane 2 performance ladder                  | 7.2 Restricted-Execution Performance |
| `7-2-oracle-corpus`                         | Speedometer 3 oracle corpus                  | 7.2 Restricted-Execution Performance |
| `7-3-v8-jitless-comparison`                 | AmberMonkey AOT-only vs V8 `--jitless`       | 7.3 Default-JIT Performance Retained  |
| `7-4-artifact-installation-cost`            | per-artifact installation cost               | 7.4 Artifact Installation Cost        |
| `7-4-artifact-installation-startup`         | JetStream 3 startup noise check              | 7.4 Artifact Installation Cost        |
| `7-5-indirection-overhead`                  | indirection microbenchmarks (perf counters)  | 7.5 Indirection Overhead              |
| `7-5-indirection-e2e-s3`                    | end-to-end Speedometer effect                | 7.5 Indirection Overhead              |
| `7-6-cross-process-memory-sharing`          | content-process memory (smaps)               | 7.6 Memory and Binary Footprint       |
| `7-6-binary-size`                           | on-disk binary size                          | 7.6 Memory and Binary Footprint       |

### Retired

| fossil                                         | topic                                        |
|------------------------------------------------|----------------------------------------------|
| `retired-3-1-jit-memory`                       | JIT allocation census on AWSY tp6            |
| `retired-3-2-intra-workload`                   | intra-workload IC concentration              |
| `retired-3-4-sm-v8-ics-micro-bench`            | SpiderMonkey/V8 IC microbenchmark            |
| `retired-7-2-ambermonkey-perf-jetstream`       | JetStream 3 performance ladder               |
| `retired-7-3-am-perf`                          | earlier AmberMonkey held-out performance run |
| `retired-7-4-indirection-overhead-raptor`      | indirection overhead via Raptor              |
| `retired-7-5-cross-process-memory-octane`      | per-process peak memory on Octane            |
| `retired-7-6-shell-memory-scaling`             | per-runtime memory scaling in jsshell        |
| `retired-7-10-cross-process-jit-memory-awsy`   | cross-process JIT memory on AWSY tp6         |

## Running

```sh
fossil --project ambermonkey-cgo list
fossil --project ambermonkey-cgo bury 7-2-ambermonkey-perf-s3 --variant default
fossil --project ambermonkey-cgo analyze 7-2-ambermonkey-perf-s3 --analysis speedometer-detail
fossil --project ambermonkey-cgo emit 7-2-ambermonkey-perf-s3 --artifact perf
fossil serve --project ambermonkey-cgo
```

Variant scripts receive the variant as argument 1. Analysis scripts receive
variant and record directory as arguments 1 and 2, with one observation JSON
on stdin. Artifact scripts receive an output directory as argument 1 and,
when configured with an analysis, aggregated metrics on stdin.

Artifacts live below `cgo-2027/artifacts/<fossil>/<artifact>/`. The scripts
choose filenames and may write JSON, PDF, and PNG together. They do not need
an output-format field or Fossil-provided environment variables.

`common/settings.py` owns build paths, mozconfigs, corpus directories, and
scratch location. `common/browser.py` and `common/shell.py` define shared
launch arguments. Each adjacent `run.py` owns its experiment's variants,
cycle counts, instrumentation, and failure behavior. Shared Raptor,
Speedometer, JetStream, and Octane parsers live in `../scripts/benchmarks`.

Runners write `AMBER_EXECUTION=` JSON lines to stderr containing the actual
launch arguments, explicit environment settings, removed environment names,
and working directory. Analyses use these captured launches for flag checks;
older records retain their expanded manifest commands. Existing manifests
and observations are preserved verbatim.

Oracle variants still require the corresponding oracle image to be built
before recording. They use the same executable paths as corpus variants;
the variant name does not select or rebuild an embedded image. Likewise,
indirection variants require the three separately prepared shell binaries.

The corpus-construction runner replaces its selected site's corpus directory.
The memory runner retains samples even when Raptor exits unsuccessfully, and
waits for its sidecar to finish before reducing the measurements.

## Style
- Fossil descriptions are one line: what is measured, not why.
- Figure scripts are decoupled from any particular variant set.
