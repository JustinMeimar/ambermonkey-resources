// Each leaf invocation combines a function-entry stack-limit check with the
// native-linkable TypeOfEqObject ABI call used by the Proxy typeof slow path.

function leaf(proxy) {
  return typeof proxy === "object" ? 1 : 0;
}

function bench() {
  const INNER = 50_000_000;
  const proxy = new Proxy({}, {});
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    n = n + leaf(proxy);
  }
  return n;
}

const r = bench();
if (r !== 50_000_000) {
  throw new Error("bad stack_abi_call sum: " + r);
}
