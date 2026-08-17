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

Numbering tracks paper sections: 3-X = Section III (Structured ICs), 6-X =
Section VI (Methodology), 7-X = Section VII (Evaluation). Retired fossils
keep a `retired-<orig-N-M>-<slug>` name so provenance stays legible.

### Active

| id  | topic                                          | paper subsection            |
|-----|------------------------------------------------|-----------------------------|
| 0-0 | hand-authored taxonomy tables                  | design tables               |
| 3-2 | intra-workload IC concentration (tp6, 8 sites) | (background)                |
| 3-3 | inter-workload overlap (tp6, 8 sites)          | III.D cross-workload reuse  |
| 6-1 | AOT corpus recorder over tp6 + self-hosted     | VI.B corpus construction    |
| 7-1 | corpus coverage on held-out workloads          | VII.A corpus coverage       |
| 7-2 | Speedometer 3 tier ladder                      | VII.B restricted execution  |
| 7-3 | AmberMonkey AOT-only vs V8 --jitless           | VII.C V8 jitless comparison |
| 7-4 | indirection microbenchmarks (perf cycles)      | VII.D indirection overhead  |
| 7-5 | Speedometer 3 content-process memory (smaps)   | VII.E cross-process memory  |
| 7-6 | on-disk binary size                            | VII.F binary size           |

### Retired

| id                                     | topic                                          |
|----------------------------------------|------------------------------------------------|
| retired-3-1-jit-memory                 | JIT allocation census on AWSY tp6              |
| retired-7-3-am-perf                    | earlier AmberMonkey held-out performance run   |
| retired-7-4-indirection-overhead-raptor| indirection overhead via Raptor                |
| retired-7-4-jetstream3-startup         | JetStream 3 startup 2x2                        |
| retired-7-5-cross-process-memory-octane| per-process peak memory on Octane              |
| retired-7-6-shell-memory-scaling       | per-runtime memory scaling in jsshell          |
| retired-7-8-aot-attachment-cost        | AOT attachment cost (cpstartup)                |
| retired-7-10-cross-process-jit-memory-awsy | cross-process JIT memory on AWSY tp6       |

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

## Style
- Fossil descriptions are one line: what is measured, not why.
- Figure scripts are decoupled from any particular variant set.
