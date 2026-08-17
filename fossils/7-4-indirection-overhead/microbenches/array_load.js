// Control microbench: monomorphic dense-array GetElem with a variable
// int32 index. Exercises the GetElem IC entry+dispatch and the array
// bounds check per iter. None of the perf 1/3/5/6/n commits target
// GetElem; this measures the AOT indirection floor on a different IC
// entry than prop_load. If opt still beats default here, the win
// generalizes beyond the four value-mirror / relocation opts.

function bench() {
  const INNER = 100_000_000;
  const arr = [1, 1, 1, 1];
  let s = 0;
  for (let i = 0; i < INNER; i++) {
    s = s + arr[i & 3];
  }
  return s;
}

const r = bench();
if (r !== 100_000_000) {
  throw new Error("bad array_load result: " + r);
}
