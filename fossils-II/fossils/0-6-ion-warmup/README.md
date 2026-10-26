# Ion warmup experiment

`0-5-ion-templates` measured whether an Ion template would already exist when a
compilation is requested. That bounds only the backend compile. A template keyed
by a synthetic or serialized compilation context could be looked up when a
function is first seen, before Baseline accrues type information, so the time
it could remove is the function's lower-tier execution before Ion installs. This
experiment records that time.

The variants and the training/evaluation structure are the same as in 0-5:
each observation runs the workload in two independent browser launches with
fresh profiles, and no cache is enabled. Build with
`just build build-browser-release` from `justin/in-memory-cache-experiments-v157`
(schema 6 Ion recurrence logging), then:

```sh
fossil bury 0-6-ion-warmup --project ambermonkey-oopsla --variant headline-hop --iterations 1
python3 fossils/0-6-ion-warmup/record.py headline-hop --dry-run
```

## Capture

Schema 6 `request` events add the root script's `filename`, `line`, `column`
(one-origin), whether the compilation is `osr`, the `warm_up_count` at request,
and two milestones of the script's lower-tier lifecycle: `jit_script_us`, when
it entered the Baseline Interpreter, and `baseline_linked_us`, when Baseline
code first linked. Either is zero when unrecorded. The analyzer copies these
onto the matching `finish` record.

Both phases run the Gecko profiler from startup (`js` feature, 1 ms interval,
main and worker threads, 1 GiB buffer per process) and write a shutdown profile
to `<phase>/profile.json`. Each sampled JS frame carries its tier: C++
interpreter, Baseline Interpreter, Baseline or Ion. Training is profiled too,
because Ion keys include whether profiler instrumentation was compiled in.

A phase fails if any process with guest Ion compilations is absent from the
profile, or if its earliest main-thread sample is later than its first Ion
request (by more than 100 ms of clock margin), which would mean the circular
buffer overwrote the warmup.

Profile frames are joined to Ion compilations by process ID and
`filename:line:column`. The engine truncates filenames to 200 bytes, as the
profiler's frame labels do.

## Measurement definitions

For each guest function whose first installed Ion compilation in an evaluation
process would have hit a template set:

- **Upper bound**: main-thread samples whose innermost JS frame is that function
  in a lower tier, from process start until that installation. This includes
  native work called from the function and Baseline compilation.
- **Scaled**: the upper bound times `1 - 1/s` for an assumed Ion speedup `s` of
  3 and 10, since with a template the function still executes, in Ion.

To stay conservative:

- Lower-tier time of an inlined callee is never attributed to its caller's
  template. It counts only if the callee has its own qualifying Ion compilation.
- Only warmup before the first installed compilation counts. Warmup after
  invalidation counts only if that is the first compilation that hits.
- Functions that never reach Ion are excluded: there would be no template to
  serve them.

The analysis script that applies these definitions is not written yet.

## Caveats

The profiler adds overhead to both phases, and its instrumentation is compiled
into every Ion and Baseline body, so absolute times are inflated relative to
unprofiled runs. A 1 ms interval is coarse per function and meaningful only in
aggregate. Profile and trace clocks are aligned through wall-clock epochs, with
roughly millisecond error. Samples landing between a successful Ion link and the
first entry into Ion code are not separated.
