# fossils

Benchmark experiments for AmberMonkey. Each subdirectory is one fossil — a
self-contained experiment with a `fossil.toml` declaring its variants,
analyses, figures, and tables.

## Layout

```
fossils/
  project.toml          shared constants (@FIREFOX, @JSSHELL, ...)
  scripts/              cross-fossil utilities (figure_style, corpus, ...)
  <N-M-slug>/
    fossil.toml         experiment definition
    scripts/            experiment-local helpers (record, reduce, ...)
    analyses/           per-observation parsers
    figures/            figure and table emitters
    records/            fossil-managed observation store (do not edit)
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

```
fossil bury <fossil>                          # run all variants
fossil bury <fossil> --variant <v1,v2...>     # run one
fossil bury <fossil> --dry-run                # print the expanded command
fossil analyze <fossil>                       # (re-)run analyses on records
fossil figure  <fossil> <figure-name>         # render a figure
fossil table   <fossil> <table-name>          # emit a JSON table
```

Variant strings are shell fragments with `@CONST` (from `project.toml`) and
`$VAR` (from the fossil's `[variables]`) substituted before execution.
Substitution is single-pass, so `$VAR` inside another variable is left
literal — inline instead of nesting.

All subprocesses receive `FOSSIL_PROJECT_DIR`, `FOSSIL_NAME`,
`FOSSIL_PREFIX`, and project constants as `FOSSIL_CONST_<NAME>`. Each also
receives its operation name: `FOSSIL_VARIANT_NAME`, `FOSSIL_ANALYSIS_NAME`,
`FOSSIL_FIGURE_NAME`, or `FOSSIL_TABLE_NAME`. Analysis scripts additionally
receive `FOSSIL_RUN_DIR` and the record's variant. External paths belong in
`project.toml`; variant commands locate fossil-local scripts below
`$FOSSIL_PROJECT_DIR/$FOSSIL_NAME`.

## Style
- Fossil descriptions are one line: what is measured, not why.
- Figure scripts are decoupled from any particular variant set.
