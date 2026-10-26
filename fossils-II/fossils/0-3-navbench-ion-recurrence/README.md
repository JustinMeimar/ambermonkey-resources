# Ion template recurrence under NavBench

How much guest Ion backend work repeats across distinct script instances in one
browser session, for the same function and the same pointer-parameterized template?

The report has two backend-time-weighted fractions: `function_recurrence` and
`template_recurrence`, plus the compilation count and total backend milliseconds.
`function_recurrence_count` and `template_recurrence_count` give the unweighted
fractions: matching compilations divided by all guest compilations, with one vote
per compilation. Both weightings use the same matches and population.
A hit requires an earlier linked compilation in the session from a different
`(pid, script)` instance. Recompilation of the same instance alone is not a hit.
All processes share the candidate pool. Self-hosted and system-realm compilations
are excluded from both the pool and denominator. Templates are matched within
function identity. There is no eviction or cross-session cache warming.

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

## Running

Build the instrumented `justin/in-memory-cache-experiments-v157` browser into
`build-browser-release`, then run inside the development environment:

```sh
fossil bury 0-3-navbench-ion-recurrence --project ambermonkey-oopsla --variant navbench --iterations 1
fossil analyze 0-3-navbench-ion-recurrence:navbench --project ambermonkey-oopsla
```

## Count recurrence figure

```sh
fossil emit 0-3-navbench-ion-recurrence --project ambermonkey-oopsla --artifact recurrence
```

The figure consumes Fossil's `recurrence` analysis and plots only
`function_recurrence_count` and `template_recurrence_count`, with equal weight
per guest compilation. By default, Fossil selects the latest record per variant;
unrecorded variants are omitted. `--variant` and `--last` use Fossil's normal
record selection. Bars show means, with standard deviations when nonzero.
The artifact directory contains `recurrence.pdf`, `recurrence.png`, and
`recurrence.json` with the plotted count metrics.

A separate figure shows the distribution of distinct template keys per function:

```sh
fossil emit 0-3-navbench-ion-recurrence --project ambermonkey-oopsla --artifact template-distribution
```

Each guest function fingerprint contributes one vote, counting its distinct
template keys across all instances in the session (including same-instance
recompilations). The figure groups counts into 1, 2, 3, 4, 5–8, 9–16, and 17+
keys, and annotates function totals and maximum keys per function. Selected
observations are averaged, rather than merging keys across sessions.
The PDF/PNG and analyzed JSON are accompanied by `templates-per-function.csv`
with every function hash and its distinct-key count. With multiple observations,
the CSV reports mean and standard deviation over observations containing that
function; absent functions are not treated as having zero templates.

## Variants

Fossil passes the variant name as the first argument to `record.py`. All variants
use that same runner; `fossil.toml` contains only the name-to-script mappings.
`navbench` uses the recorded NavBench sequence with visits to YouTube, Reddit,
X/Twitter, and LinkedIn filtered out, including their measurements and interactions.
The runner overrides the manifest commands with this filtered sequence.
The ten additional
variants run **live, signed out**, using the approved routes in `../common/navbench_routes.toml`:

| Variant | Route (one pass) |
| --- | --- |
| `workspace-shuffle` | Docs A → Sheets → Docs A → Slides → Sheets → Docs B |
| `media-pinball` | Bluesky → Substack |
| `wiki-rabbit-hole` | Mandelbrot set → Fractal → Julia set → Complex number → Complex dynamics → Julia set → Mandelbrot set |
| `cake-quest` | Sally's → Preppy Kitchen → King Arthur → Sally's → King Arthur flourless → Preppy Kitchen |
| `compiler-coffee` | Maglev → Branch prediction → Sparkplug → Input latency → Maglev → Branch prediction |
| `debugging-detour` | MDN Promise → async function → MDN GitHub issues → Using promises → Promise → GitHub issues |
| `headline-hop` | BBC → Guardian report → NASA → Guardian analysis → BBC → Guardian report |
| `comparison-cart` | Amazon XM5 → RTINGS XM5 → Best Buy XM5 → Amazon XM4 → RTINGS XM5 → Amazon XM5 |
| `weekend-wayfinder` | Maps Banff → Wikipedia Banff → Fairmont → Gondola → Maps Banff → Fairmont |
| `paper-trail` | Attention abstract → Attention HTML → BERT abstract → BERT HTML → Attention HTML → BERT abstract |

Each new variant performs two passes in a single cold browser session: 12 visits,
except `wiki-rabbit-hole` (14) and `media-pinball` (4). Both the driver's startup
delay and the route warmup are disabled. It waits three seconds after each
navigation, then navigates to `about:blank` for one second. The second pass
retains the first pass's HTTP cache. Every visit
gets a unique measurement alias. These are hard navigations with NavBench's
BFCache-disabling preferences; they do not simulate retained tabs or back/forward.
There is no login or editing of the public documents.

The live runner invokes `mach browsertime` with NavBench's interactive driver,
avoiding the baseline manifest's replay-only DNS override and Raptor's unrelated
pageload-summary requirements. It builds a fresh profile from Raptor's base
profile directories and preserves NavBench's BFCache and HTTP/3/Alt-Svc
preferences. The Ion recurrence analyzer and instrumentation are shared across
all variants. Live runs also retain Browsertime's per-visit results, and the
recorder rejects missing visits and reported command/navigation errors.
The recorded `navbench` baseline retains its original warmup settings.
It records the mode, resolved commands, and workload source hash in each
observation and in `workload.json` alongside the trace. Live content and network
conditions can change; these results are not controlled replay comparisons with
the `navbench` baseline. A live page can also present a consent screen or access
challenge, so inspect harness output/screenshots when validating a new route.

```sh
# Inspect a resolved sequence without launching Firefox:
python3 0-3-navbench-ion-recurrence/record.py cake-quest --dry-run

# Run a selected variant using the normal Fossil interface:
fossil bury 0-3-navbench-ion-recurrence --project ambermonkey-oopsla --variant cake-quest --iterations 1
fossil analyze 0-3-navbench-ion-recurrence:cake-quest --project ambermonkey-oopsla

# Run every variant, including the recorded baseline, once:
fossil bury 0-3-navbench-ion-recurrence --project ambermonkey-oopsla --iterations 1
```

Each iteration runs one cold browser session. Fossil stores the browser's `IONREC`
compilation events in the observation. NavBench stdout/stderr stays in
`$FIREFOX_ROOT/artifacts/ion-recurrence/<timestamp>-<variant>/harness.log` alongside raw traces.
The recorder requires schema 2 instrumentation and fails on empty guest data.
The analyzer can still read old directory-only observations: their template key
has the same definition, but their backend timing includes the removed MIR hashing.

These are observed recurrence fractions, not navigation speedups or realizable
cache hit rates. Linked-event order does not account for overlapping compilation.
Recorded-page revisits and short interactions constrain workload coverage.
Script identity currently uses addresses and can be affected by address reuse.
