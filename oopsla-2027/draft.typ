

= Draft

Some thoughts in ~/.jot/research/

- Compilers use heurisitics -- simple functions which approximate an optimal
  decision, such as inlining or tiering in a JIT. Heuristics are typically
  chosen by experts to take specific values. Profiling can discover cases
  where heuristics diverge significantly from the optimal decision. For instance,
  SpiderMonkey introduced JitHints to indicate certain functions observed
  during profiling as executing frequently to be annotated such that the
  optimized compilation warmup threshold would be elided.

  The premise of this work is to synthesis and apply hints at run-time,
  across runtime boundaries, covering the cases which profiling, which is
  inherintly limited to only approximate common workloads, can not cover.
  Specifically, we learn online the functions which are hot and synthesize
  compilation hints to guide their eager compilation through the JIT tiering
  process.

    - We use existing hints and create several new hints. Note that the
      existing JitHints implementation already uses prior page information,
      not simply profiling data. So this is not novel.
 
- Compilation patterns in browsers reveals strong temporal and structural
  recurrence over isolated cross-runtime boundaries which JIT compilers
  remain unaware of.

- Effort spent optimizing single page JavaScript execution. Less effort
  spent on the browser as a whole.

  - Standard web-benchmarks like Speedometer3 and Jestream3 are designed for
    single page, which makes measuring the contribution against other
    implementations less straightforward. Do we need to create our own
    benchmarks?

  - We can measure speedometer3 cold v.s speedometer 3 hot? That is somewhat
    contrived, but it does isolate the contribution of the cache + hints.

- A global code cache on it's own is no-where near a novel contribution.
  Niether is JIT hinting. We either need to travel down the prediction
  pathway, or, or.. hmm

= Abstract

= Introduction


