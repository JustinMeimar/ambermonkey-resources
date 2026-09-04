// A Proxy forces CacheIR's LoadTypeOfEqObjectResult slow check, which emits
// callWithABI<TypeOfEqObject>. The target is in ABIFUNCTION_LOCAL_LIST. The
// proxy and handler are allocated once, so the loop exercises one local ABI
// call per iteration without allocation or GC.

function bench() {
  const INNER = 50_000_000;
  const proxy = new Proxy({}, {});
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    if (typeof proxy === "object") {
      n = n + 1;
    }
  }
  return n;
}

const r = bench();
if (r !== 50_000_000) {
  throw new Error("bad abi_call sum: " + r);
}
