

- ShareJIT. We've seen this while working on AmberMonkey. They turn off some
  optimizations in order to make the code-representation less coupled,
  presumably, which increases sharing. This is for the Android runtime, hence
  JVM.

- TrueJIT (MLPR 2026) predicts sequnces of JIT compilation to minimize latency
  using a LSTM.

- Reusing Just-in-Time Compiled Code (OOPSLA 2023)
  [(https://janvitek.org/pubs/oopsla23.pdf)](<https://janvitek.org/pubs/oopsla23.pdf>)

- This is weird, seemingly unpublished:
  https://zoranzhao.github.io/docs/browser_2013.pdf
