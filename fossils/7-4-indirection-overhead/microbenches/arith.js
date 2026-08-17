// Control microbench: pure integer arithmetic (Add, Mul, Sub) in a tight
// loop. None of the perf 1/3/5/6/n commits target BinOp ICs specifically;
// this measures the AOT indirection floor on ops that do not benefit from
// value mirroring or callWithABI-relocation. If opt still beats default
// here, the win generalizes beyond the four targeted opts.
//
// Body designed for net +1 per iter so the accumulator stays under 2^31-1
// at INNER = 1e8.

function bench() {
  const INNER = 100_000_000;
  let s = 0;
  for (let i = 0; i < INNER; i++) {
    s = s + 2 * 1 - 1;
  }
  return s;
}

const r = bench();
if (r !== 100_000_000) {
  throw new Error("bad arith result: " + r);
}
