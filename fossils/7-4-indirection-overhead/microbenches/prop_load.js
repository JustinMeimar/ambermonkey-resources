// Control microbench: monomorphic GetProp on a fixed shape. Exercises the
// GetProp IC entry+dispatch path, which none of the perf 1/3/5/6/n
// commits specifically target. Isolates the AOT indirection floor on IC
// entry cost. If opt still beats default here, the win generalizes
// beyond the four value-mirror / relocation opts.

function bench() {
  const INNER = 100_000_000;
  const obj = { x: 1 };
  let s = 0;
  for (let i = 0; i < INNER; i++) {
    s = s + obj.x;
  }
  return s;
}

const r = bench();
if (r !== 100_000_000) {
  throw new Error("bad prop_load result: " + r);
}
