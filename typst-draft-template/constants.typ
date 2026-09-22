// Paper-facing named citations grouped by source fossil.
// Each entry composes a JSON accessor (json-field / cell-value /
// cell-from-table) with a formatter (pct / mb / kb / int-str / words)
// so the draft can read a bare `#foo` and get a ready-to-print string.

#import "lib/tables.typ": cell-value, json-field, cell-from-table
#import "lib/configurations.typ": config-name, config-short, config-prose
#import "lib/cite.typ": *


// --- Execution-configuration display-name aliases ---
// Never write "AmberMonkey" / "Baseline JIT" / etc. as literal strings in
// prose or captions. Use these constants so the whole paper tracks the
// registry at fossils/configurations.toml.
#let interp-only-name = config-name("interp-only")
#let interp-only-prose = config-prose("interp-only")
#let am     = config-prose("aot-corpus")
#let am-ic  = config-prose("aot-corpus-ic")
#let am-ion = config-prose("aot")
#let baseline-jit = config-prose("default-no-ion")
#let default-ion  = config-prose("default")


// --- 7-1 corpus construction (complete tp6-Train union) ---
#let tp6-train-site-count = int-str(json-field("7-1-composition.json", "train_site_count"))
#let tp6-test-site-count  = int-str(json-field("7-1-composition.json", "test_site_count"))
#let tp6-site-count       = int-str(json-field("7-1-composition.json", "total_site_count"))
#let ic-stub-count        = int-str(json-field("7-1-composition.json", "train_union_ic_count"))
#let ic-stub-bytes        = kb(json-field("7-1-composition.json", "train_union_ic_bytes"))
#let self-hosted-fn-count = int-str(json-field("7-1-composition.json", "self_hosted_function_count"))

#let _loso-ic       = json-field("7-1-loso.json", "kinds").ic
#let loso-ic-min    = pct(_loso-ic.min_pct / 100, digits: 1)
#let loso-ic-max    = pct(_loso-ic.max_pct / 100)
#let loso-ic-median = pct(_loso-ic.median_pct / 100, digits: 1)


// --- 3-3 inter-workload coverage ---
#let _ic-static  = json-field("inter-workload-coverage.json", "ic").static
#let _ic-dyn     = json-field("inter-workload-coverage.json", "ic").dynamic
#let _bl-static  = json-field("inter-workload-coverage.json", "baseline").static
#let _bl-dyn     = json-field("inter-workload-coverage.json", "baseline").dynamic

#let inter-site-count              = int-str(json-field("inter-workload-coverage.json", "site_count"))
#let inter-static-pair-count       = int-str(json-field("inter-workload-coverage.json", "static_pair_count"))
#let inter-dynamic-direction-count = int-str(json-field("inter-workload-coverage.json", "off_diagonal_count"))

#let inter-ic-static-median  = pct(_ic-static.median)
#let inter-ic-dyn-median     = pct(_ic-dyn.median)
#let inter-ic-dyn-iqr        = iqr-pct(_ic-dyn)

#let inter-baseline-static-median = pct(_bl-static.median)
#let inter-baseline-dyn-median    = pct(_bl-dyn.median)
#let inter-baseline-dyn-iqr       = iqr-pct(_bl-dyn)

#let _inter-growth-points = json-field("3-3-corpus-growth.json", "points")
#let _inter-growth-first  = _inter-growth-points.at(0)
#let _inter-growth-twenty = _inter-growth-points.at(19)
#let _inter-growth-final  = _inter-growth-points.at(23)

#let inter-ic-dynamic-first = pct(_inter-growth-first.ic_dynamic, digits: 1)
#let inter-ic-dynamic-final = pct(_inter-growth-final.ic_dynamic, digits: 2)
#let inter-ic-dynamic-tail-gain = float-str(
  (_inter-growth-final.ic_dynamic - _inter-growth-twenty.ic_dynamic) * 100,
  digits: 2,
)
#let inter-baseline-dynamic-final = pct(_inter-growth-final.baseline_dynamic, digits: 1)


// --- 7-2 held-out corpus coverage ---
#let sp3-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "speedometer3")
#let js3-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "jetstream3")
#let tp6-test-ic-hit-rate = cell-from-table("7-2-ic-table.json", "AOT hit rate", "tp6_test")


// --- 7-3 restricted-execution Speedometer perf ---
// Ratios come from the tier-ladder table's aggregate score; the ratio equals
// the geometric mean of the 20 per-workload speedups.
#let _sp3-aot-ratio      = cell-value("restricted-execution-perf.json", "aot-corpus",     "ratio_over_interp")
#let _sp3-aot-ic-ratio   = cell-value("restricted-execution-perf.json", "aot-corpus-ic",  "ratio_over_interp")
#let _sp3-bl-ratio       = cell-value("restricted-execution-perf.json", "default-no-ion", "ratio_over_interp")
#let _sp3-default-ratio  = cell-value("restricted-execution-perf.json", "default",        "ratio_over_interp")
#let sp3-aot-speedup           = pct(json-field("restricted-execution-perf.json", "aot_over_interp_speedup"))
#let sp3-aot-ic-speedup        = pct(json-field("restricted-execution-perf.json", "aot_ic_over_interp_speedup"))
#let sp3-aot-default-fraction  = pct(json-field("restricted-execution-perf.json", "aot_over_default_ratio"))
#let sp3-aot-ratio             = float-str(_sp3-aot-ratio)     + "×"
#let sp3-aot-ic-ratio          = float-str(_sp3-aot-ic-ratio)  + "×"
#let sp3-bl-ratio              = float-str(_sp3-bl-ratio)      + "×"
#let sp3-default-ratio         = float-str(_sp3-default-ratio) + "×"
#let sp3-aot-over-bl-fraction  = pct(_sp3-aot-ratio / _sp3-bl-ratio)
#let sp3-workload-count        = int-str(20)


// --- Speedometer 3 engine-memory reduction at Peak ---
// Compare the Ion-disabled runtime-Baseline and AOT-only configurations so
// both measurements have the same tier ceiling.
#let _jit-memory-runtime-pss = cell-value("cross-process-memory-sharing-aggregate.json", "default-no-ion", "per_proc_engine_pss_mb")
#let _jit-memory-aot-pss     = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus",     "per_proc_engine_pss_mb")
#let jit-memory-reduction    = pct(1 - _jit-memory-aot-pss / _jit-memory-runtime-pss)


// --- 7-7 indirection microbenchmark aggregate (Geometric mean row) ---
#let indirection-reps            = json-field("7-7-cycles.json", "repetitions_per_configuration")
#let indirection-benchmark-count = words(json-field("7-7-cycles.json", "benchmark_count"))
#let indirection-targeted-count  = words(json-field("7-7-cycles.json", "targeted_benchmark_count"))
#let indirection-control-count   = words(json-field("7-7-cycles.json", "control_benchmark_count"))
#let indirection-repetitions     = words(indirection-reps)
#let indirection-process-word    = if indirection-reps == 1 { "process" } else { "processes" }
#let indirection-ratio           = float-str(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ratio")) + "×"
#let indirection-overhead        = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_overhead"))
#let indirection-ipi-overhead    = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ipi_overhead"))
#let indirection-ipc-delta       = pct(cell-value("7-7-cycles.json", "Geometric mean", "aot_over_runtime_ipc_delta"))


// --- 7-10 AWSY cross-process JIT memory (TabsOpenForceGC anchor) ---
#let _awsy-stock-engine-pss      = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "engine_pss_mb")
#let _awsy-aot-engine-pss        = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "engine_pss_mb")
#let _awsy-stock-per-proc-pss    = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "per_proc_engine_pss_mb")
#let _awsy-aot-per-proc-pss      = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "per_proc_engine_pss_mb")
#let _awsy-stock-anon-exec-pss   = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "anon_exec_pss_mb")
#let _awsy-aot-anon-exec-pss     = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "anon_exec_pss_mb")
#let _awsy-stock-libxul-exec-pss = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "libxul_exec_pss_mb")
#let _awsy-aot-libxul-exec-pss   = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "libxul_exec_pss_mb")
#let _awsy-stock-libxul-exec-rss = cell-value("7-10-aggregate.json", "awsy-tp6-stock",    "libxul_exec_rss_mb")
#let _awsy-aot-libxul-exec-rss   = cell-value("7-10-aggregate.json", "awsy-tp6-aot-only", "libxul_exec_rss_mb")

#let awsy-content-procs           = int-str(cell-value("7-10-aggregate.json", "awsy-tp6-stock", "n_procs"))
#let awsy-stock-engine-pss        = mb-str(_awsy-stock-engine-pss)
#let awsy-aot-engine-pss          = mb-str(_awsy-aot-engine-pss)
#let awsy-stock-per-proc-pss      = mb-str(_awsy-stock-per-proc-pss)
#let awsy-aot-per-proc-pss        = mb-str(_awsy-aot-per-proc-pss)
#let awsy-engine-pss-reduction    = pct(1 - _awsy-aot-engine-pss / _awsy-stock-engine-pss)
#let awsy-per-proc-pss-reduction  = pct(1 - _awsy-aot-per-proc-pss / _awsy-stock-per-proc-pss)
#let awsy-anon-exec-pss-reduction = pct(1 - _awsy-aot-anon-exec-pss / _awsy-stock-anon-exec-pss)
#let awsy-libxul-exec-rss-growth  = pct(_awsy-aot-libxul-exec-rss / _awsy-stock-libxul-exec-rss - 1)
#let awsy-stock-libxul-sharing    = float-str(_awsy-stock-libxul-exec-rss / _awsy-stock-libxul-exec-pss, digits: 1) + "×"
#let awsy-aot-libxul-sharing      = float-str(_awsy-aot-libxul-exec-rss / _awsy-aot-libxul-exec-pss, digits: 1) + "×"


// --- 7-11 Speedometer 3 cross-process sharing (Peak checkpoint) ---
// Sourced from the aggregate-table rows so the numbers in prose track the
// figure automatically. Intentionally does not export a reduction-vs-stock
// scalar: aot-corpus runs a different tier profile than stock, so no direct
// engine-PSS delta is defensible. The matched no-Ion comparison is above.
#let _sp3-stock-libxul-exec-pss = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "libxul_exec_pss_mb")
#let _sp3-aot-libxul-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "libxul_exec_pss_mb")
#let _sp3-stock-libxul-exec-rss = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "libxul_exec_rss_mb")
#let _sp3-aot-libxul-exec-rss   = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "libxul_exec_rss_mb")
#let _sp3-stock-anon-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "anon_exec_pss_mb")
#let _sp3-aot-anon-exec-pss     = cell-value("cross-process-memory-sharing-aggregate.json", "aot-corpus", "anon_exec_pss_mb")
#let _sp3-stock-per-proc-pss    = cell-value("cross-process-memory-sharing-aggregate.json", "default",    "per_proc_engine_pss_mb")
#let _sp3-runtime-per-proc-pss  = _jit-memory-runtime-pss
#let _sp3-aot-per-proc-pss      = _jit-memory-aot-pss

#let sp3-content-procs           = int-str(cell-value("cross-process-memory-sharing-aggregate.json", "default", "n_procs"))
#let sp3-stock-per-proc-pss      = mb-str(_sp3-stock-per-proc-pss)
#let sp3-runtime-per-proc-pss    = mb-str(_sp3-runtime-per-proc-pss)
#let sp3-aot-per-proc-pss        = mb-str(_sp3-aot-per-proc-pss)
#let sp3-stock-anon-exec-pss     = mb-str(_sp3-stock-anon-exec-pss)
#let sp3-aot-anon-exec-pss       = mb-str(_sp3-aot-anon-exec-pss)
#let sp3-stock-libxul-sharing    = float-str(_sp3-stock-libxul-exec-rss / _sp3-stock-libxul-exec-pss, digits: 1) + "×"
#let sp3-aot-libxul-sharing      = float-str(_sp3-aot-libxul-exec-rss / _sp3-aot-libxul-exec-pss, digits: 1) + "×"

// Marginal cost of adding the AOT image, expressed both as physical PSS
// growth and as mapped RSS growth. The RSS/PSS ratio of the delta captures
// how effectively the new file-backed pages are shared across content procs.
#let _sp3-image-pss-growth       = _sp3-aot-libxul-exec-pss - _sp3-stock-libxul-exec-pss
#let _sp3-image-rss-growth       = _sp3-aot-libxul-exec-rss - _sp3-stock-libxul-exec-rss
#let sp3-image-pss-growth        = mb-str(_sp3-image-pss-growth, digits: 1)
#let sp3-image-rss-growth        = mb-str(_sp3-image-rss-growth, digits: 1)
#let sp3-image-sharing-amplification = float-str(_sp3-image-rss-growth / _sp3-image-pss-growth, digits: 1) + "×"

// interp-only floor: no JIT backend attached, so anon-exec should be zero.
// Its per-proc engine PSS is the shared-image contribution alone, and gives
// the lower bound the JIT configurations are measured against.
#let _sp3-interp-anon-exec-pss   = cell-value("cross-process-memory-sharing-aggregate.json", "interp-only", "anon_exec_pss_mb")
#let _sp3-interp-per-proc-pss    = cell-value("cross-process-memory-sharing-aggregate.json", "interp-only", "per_proc_engine_pss_mb")
#let sp3-interp-anon-exec-pss    = mb-str(_sp3-interp-anon-exec-pss)
#let sp3-interp-per-proc-pss     = mb-str(_sp3-interp-per-proc-pss)


// --- 7-9 binary-size impact (libxul-focused) ---
// Row labels match the human-readable "Configuration" column of 7-9-libxul.json.
#let _libxul-default = cell-value("7-9-libxul.json", "Default JIT",       "pt_load_bytes")
#let _libxul-aot     = cell-value("7-9-libxul.json", "Default JIT + AOT", "pt_load_bytes")
#let _libxul-image   = cell-value("7-9-libxul.json", "Default JIT + AOT", "linked_image_bytes")
#let _libxul-growth  = _libxul-aot - _libxul-default
#let libxul-default-size = mb(_libxul-default)
#let libxul-aot-size     = mb(_libxul-aot)
#let libxul-growth       = mb(_libxul-growth)
#let libxul-growth-pct   = pct(_libxul-growth / _libxul-default, digits: 2)
#let aot-image-size      = mb(_libxul-image)
#let corpus-packed-size  = mb(cell-value("7-9-libxul.json", "Default JIT + AOT", "packed_image_bytes"))
#let nonimage-growth     = kb(_libxul-growth - _libxul-image)

