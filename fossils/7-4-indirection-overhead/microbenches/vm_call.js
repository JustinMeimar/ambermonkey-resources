// UNVERIFIED CANDIDATE. Intended to exercise callVMInternal per iter to
// isolate perf 5/n (2 loads + call -> 1 load + memory-operand call).
//
// Object.keys allocates a fresh array via a VM call in the baseline
// interpreter. The allocation adds GC pressure but keeps the VM-call
// site hot. Before quoting numbers, verify with IONFLAGS=bl-aot that
// the emitted code for this op goes through callVMInternal on both
// $JSSHELL_DEFAULT and $JSSHELL_OPT, and that the fast paths did not
// intrinsify it away. If they did, swap for Reflect.ownKeys, a slow
// Symbol.for("..."), or a controlled throw/catch. Also worth
// double-checking that the GC isn't dominating; a nursery-only alloc
// path should keep per-iter cost stable.

function bench() {
  const INNER = 20_000_000;
  const obj = { a: 1, b: 2, c: 3 };
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    const k = Object.keys(obj);
    n = n + k.length;
  }
  return n;
}

const r = bench();
if (r !== 60_000_000) {
  throw new Error("bad vm_call sum: " + r);
}
