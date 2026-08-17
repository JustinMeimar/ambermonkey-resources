// Pre-barrier guard: SetProp on a slot that holds a GC pointer emits a
// pre-barrier check per store. The guard load happens every iter even
// when the barrier does not actually fire (no incremental GC in progress),
// so a tight hot-store loop isolates the guard cost. Perf 1/n mirrored
// the prebarrier-zone offsets: 4 loads -> 2 loads in AOT.
//
// Warm the SetProp stub with a stable shape and pointer type by writing
// the same GC-thing repeatedly. The pre-barrier still reads the guard.

function bench() {
  const INNER = 500_000_000;
  const holder = { f: null };
  const gcThing = { x: 1 };
  for (let i = 0; i < INNER; i++) {
    holder.f = gcThing;
  }
  return holder.f;
}

const r = bench();
if (r === null || r.x !== 1) {
  throw new Error("bad prebarrier result");
}
