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
(schema 7 Ion recurrence logging), then:

```sh
fossil bury 0-6-ion-warmup --project ambermonkey-oopsla --variant headline-hop --iterations 1
python3 fossils/0-6-ion-warmup/record.py headline-hop --dry-run
```

## Capture

Schema 7 `request` events add the root script's profiler `label` (the string the
Gecko profiler labels its frames with), the requesting thread's `tid`, the realm's profiler ID (`realm`), whether
the compilation is `osr`, the `warm_up_count` at request, `process_start_us`
(process creation on the trace's wall-anchored clock), and two milestones of the
script's current JitScript: `jit_script_us`, when it was created (entry to the
Baseline Interpreter), and `baseline_linked_us`, when Baseline code first linked.
A third milestone, `last_ic_stub_us`, is the latest
IC stub attachment credited to the script before the request (inlined ICs count
for their root), with `warm_up_count_at_last_ic_stub` beside it; this is the
point JIT hints key their threshold on. `ion_threshold` is the script's Ion
threshold at request. Milestones are zero when unrecorded. The analyzer copies these onto the
matching `finish` record.

Both phases run the Gecko profiler from startup (`js,cpu` features, 1 ms interval,
main and worker threads, 1 GiB buffer per process) and write a shutdown profile
to `<phase>/profile.json`. Each sampled JS frame carries its tier: C++
interpreter, Baseline Interpreter, Baseline or Ion. Training is profiled too,
because Ion keys include whether profiler instrumentation was compiled in.

Every variant runs headless (`MOZ_HEADLESS=1`), routes included, unlike 0-5.
Live sites may treat a headless browser differently (consent screens, bot
checks); each phase still fails if any visit is missing or reports an error.

Both phases run with `javascript.options.jithints` off, so every script waits for
the default Ion threshold and the timeline is the unhinted counterfactual. What
hints would save is derived from it (the `settled` phase) rather than mixed into
it. The analysis reports `hinted_threshold_requests`, which must be zero.

Profile samples are joined to compilations by `(pid, tid, realm, label)`. Profile
frames carry the realm's profiler ID as their inner window ID, so copies of one
script in several realms on a thread (Speedometer loads each suite into a fresh
iframe, ten times) are attributed separately. JS samples without a realm ID are
reported as `no_realm_js_ms` and not attributed. Sample times
are relative to process creation, the same instant as `process_start_us`, so
trace milestones map onto the sample timeline exactly, without a clock margin.
The interpreter's frame labels are truncated to 511 bytes, so both sides are
compared on that prefix. `max_process_start_skew_us` reports the disagreement
between the profile's own wall-clock start and `process_start_us` as a check.

A phase fails if a thread with guest Ion compilations is absent from the
profile, or if its earliest sample is later than its earliest JitScript
creation, which would mean the circular buffer overwrote the warmup.

## Measurement definitions

Attribution and replay live in `$FIREFOX_ROOT/js/src/jit/ion_recurrence.py`
(`classify`, `read_profile`, `warmup`); `analyze.py` only aggregates. A sample is
attributed to the innermost JS frame on its stack, and split by what ran below
that frame: the JS itself (`js_code`), main-thread Baseline or Ion compilation
(`jit_compiler`, from the profiler's compilation labels), or any other categorized
native frame (`native_calls`, mostly DOM). Each sample
weighs one interval; `cpu_ms` instead weighs it by the thread CPU time since the
previous sample.

A function is a `(pid, tid, realm, label)` group of guest compilations with valid
keys. Groups whose label is empty or realm unknown, which map to more than one
function hash, or with no installed compilation are excluded and counted. For the rest, the first
installed compilation (earliest link) decides everything:

- **Class** per template set (`runtime`, `session`, `training`): `exact` if a
  template with its key existed, `function` if only templates for its function
  existed, `new` otherwise.
- **Lower-tier time**: samples in the interpreter, Baseline Interpreter or
  Baseline before that link, by tier and by phase:
  - `feedback`: until the last IC stub attached. Warp needs this feedback, so
    hints cannot remove it; only a template chosen before any feedback can.
  - `settled`: from there to the group's first Ion request. This is what hints
    remove, since they set the threshold to the warmup count at the last IC stub
    plus 10 (at least 210 with pretenured allocation sites).
  - `compiling`: request to link, including the wait for lazy linking. Templates
    remove the backend; hints do not.

  A script without IC stub attachments has no `feedback` phase.
- **Predicted**: a function whose installed template is among the training
  session's one (`top1`) or two (`top2`) most frequently installed templates for
  it. Its `feedback` time is the part a template chosen at first sight could
  remove; an `exact` class alone does not establish that.
- **Scaled**: exact-class `js_code` time times `1 - 1/s` for an assumed Ion
  speedup `s` of 3 and 10, since with a template the function still executes, in
  Ion. Native callees run the same either way and are not scaled.

Also reported: lower-tier and Ion samples after the first link (invalidation
churn and lazy entry, never attributed), Ion samples before it (`inlined_in_ion`:
the function inlined into an already compiled caller), and every thread's
samples by tier as context.

To stay conservative:

- Lower-tier time of an inlined callee is never attributed to its caller's
  template. It counts only if the callee has its own qualifying Ion compilation.
- Several scripts sharing a label within one realm and thread form one group,
  which stops at the earliest link among them.
- Functions that never install Ion code are excluded: there would be no
  template to serve them.

## Caveats

The profiler adds overhead to both phases, and its instrumentation is compiled
into every Ion and Baseline body, so absolute times are inflated relative to
unprofiled runs. A 1 ms interval is coarse per function and meaningful only in
aggregate. Samples landing between a successful Ion link and the first entry
into Ion code fall under `after_install`. `jit_script_us` describes the current
JitScript, so a script whose JitScript was discarded and recreated reports the
later creation.
