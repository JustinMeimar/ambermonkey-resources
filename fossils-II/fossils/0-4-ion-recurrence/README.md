# Ion recurrence in a directly launched Firefox session

A manual-browsing counterpart to `0-3-navbench-ion-recurrence`. The ten approved
workloads retain their names and URLs, but the runner launches the instrumented
Firefox binary directly. There is no NavBench, Raptor, Browsertime, WebDriver,
Marionette, replay proxy, automatic navigation, or warmup delay.

## Running

Use the development environment and a schema 2 instrumented
`build-browser-release` browser:

```sh
fossil bury 0-4-ion-recurrence --project ambermonkey-oopsla --variant cake-quest --iterations 1
fossil analyze 0-4-ion-recurrence:cake-quest --project ambermonkey-oopsla
```

Fossil passes the variant name as the first argument to `record.py`. Each run
opens the first URL in a fresh, separate Firefox profile and prints the suggested
route to the terminal. Browse manually, then close that Firefox instance to end
the observation. The suggested route has two passes; actual navigation order,
dwell times, and completion are not enforced or verified. The variant is a
session label, not proof that its full route was executed.

`workloads.toml` contains the same ten approved routes as 0-3. `fossil.toml` maps
all ten names to the same runner. The old recorded `navbench` variant and prior
observations are not part of this new experiment. Default iterations is one,
since each iteration requires manual browsing. Omitting `--variant` launches
all ten sessions sequentially, waiting for you to close each browser.

```sh
python3 0-4-ion-recurrence/record.py workspace-shuffle --dry-run
```

Firefox uses normal profile defaults, including normal BFCache and networking
behavior. Only first-run/default-browser prompts are suppressed. The runner
removes inherited harness automation variables and enables Ion logging. It does
not use an existing personal profile or sign into any sites. CAPTCHA behavior
still depends on the sites and network; this setup does not guarantee it will
eliminate challenges.

The recorder waits for Firefox to exit, validates the trace, then emits `IONREC`
events and metadata for Fossil. Logs, the profile, and `workload.json` remain in
`$FIREFOX_ROOT/artifacts/ion-recurrence-direct/<timestamp>-<variant>/`. The resolved
suggested route and its source hash are stored with each observation, explicitly
marked `manual-live` and `route_enforced: false`. Empty guest data is rejected.

## Metrics

The analyzer is copied unchanged from 0-3. `function_recurrence` and
`template_recurrence` are backend-compilation-time-weighted fractions;
`function_recurrence_count` and `template_recurrence_count` are compilation-count
fractions. A hit requires an earlier linked compilation from a different
`(pid, script)` instance. System and self-hosted compilations are excluded.
Each run starts a new candidate pool shared across its processes.

Manual sessions and normal browser defaults differ from 0-3's scripted,
BFCache-disabled workloads. Compare them as different browsing conditions,
not identical workloads with only the harness changed.

## Template contract

The prospective design uses a fixed specialization with per-instance pointer
bindings. Types, slot offsets, numeric constants, inlining and allocation choices
remain specialized. It does not parameterize every guest-dependent decision.

`function` fingerprints root source text and immutable script flags. If source
text is unavailable, it falls back to filename and source extent.

`template` fingerprints the traversal implemented by `SnapshotDescriber` in
`js/src/jit/IonRecurrence.cpp`:

- Root and inlined script source fingerprints and bytecode, and the inline tree.
- Operation snapshot kinds and bytecode offsets; CacheIR instruction bytes.
- Scalar stub fields, including slot offsets, numeric values and allocation heap
  choices; import slots, polymorphic types and environment kind.
- Recorded bailout-history and fuse flags, OSR offset, nursery allocation choices
  and profiler instrumentation setting.
- References replaced by their kind and first-appearance ordinal, with zero for
  null. Repeated references retain the same ordinal, preserving aliasing across
  the snapshot. Referent addresses, shape layouts and string contents are not
  included as binding values.

Equality means the recorded specialization inputs agree modulo pointer bindings.
A future backend must treat those bindings as parameters, and explicitly validate
any properties it uses to specialize code. The current backend can inspect
referents: this experiment measures candidates for that design, not proof of
interchangeable existing machine code or a completed binding implementation.
The fingerprints are 64-bit hashes, not collision-free identities.

These are observed recurrence fractions, not navigation speedups or realizable
cache hit rates. Linked-event order does not account for overlapping compilation.
Script identity currently uses addresses and can be affected by address reuse.
