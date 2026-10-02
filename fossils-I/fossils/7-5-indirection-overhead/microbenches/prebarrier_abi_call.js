// Each iteration combines an inactive pre-barrier guard with the
// native-linkable TypeOfEqObject ABI call used by the Proxy typeof slow path.

function bench() {
  const INNER = 50_000_000;
  const holder = { f: null };
  const gcThing = { x: 1 };
  const proxy = new Proxy({}, {});
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    holder.f = gcThing;
    if (typeof proxy === "object") {
      n = n + 1;
    }
  }
  return n + holder.f.x;
}

const r = bench();
if (r !== 50_000_001) {
  throw new Error("bad prebarrier_abi_call sum: " + r);
}
