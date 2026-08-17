// Stack-limit check fires on every function entry. Calling a trivial leaf
// once per iteration exercises this per iter. Isolates perf 1/n's
// stack-limit mirror (3 loads -> 1 load in AOT). Baseline interpreter
// entry always runs the check, so no need to disable Ion / tiering.
//
// Nested to keep both the induction var and the accumulator strictly under
// int32 max; leaf returns 1 so the sum grows deterministically.

function leaf() {
  return 1;
}

function bench() {
  const INNER = 100_000_000;
  const OUTER = 5;
  let outer_s = 0;
  for (let o = 0; o < OUTER; o++) {
    let s = 0;
    for (let i = 0; i < INNER; i++) {
      s = s + leaf();
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
