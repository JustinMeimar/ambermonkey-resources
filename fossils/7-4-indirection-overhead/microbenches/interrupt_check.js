// Hot loop stressing the interrupt-check slot and bytecode dispatch. Both are
// affected by the value-mirror opts (perf 1/n, perf 6/n): the loop back-edge
// reads the interrupt flag on every iteration, and under NO_OPTS that read
// costs two loads instead of one.
//
// Nested to keep both the induction var and the accumulator strictly under
// int32 max (2^31-1). Crossing that boundary triggers an int -> double
// transition in the interpreter mid-run and pollutes the per-iter cost.

function bench() {
  const INNER = 2_000_000_000;
  const OUTER = 5;
  let outer_s = 0;
  for (let o = 0; o < OUTER; o++) {
    let s = 0;
    for (let i = 0; i < INNER; i++) {
      s = s + 1;
    }
    if (s !== INNER) {
      throw new Error("bad inner sum: " + s);
    }
    outer_s = outer_s + 1;
  }
  return outer_s;
}

const r = bench();
if (r !== 5) {
  throw new Error("bad outer: " + r);
}
