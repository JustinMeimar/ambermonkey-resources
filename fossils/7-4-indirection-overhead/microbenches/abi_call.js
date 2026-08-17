// UNVERIFIED CANDIDATE. Intended to exercise callWithABI to a local
// (not preemptible) ABI function, isolating perf 3/n (movabs+call
// through indirection -> call rel32 via static-linker relocation).
//
// `typeof obj` in the baseline interpreter falls through to a helper
// that ultimately dispatches to js::TypeOfObject, which is in the
// ABIFUNCTION_LOCAL_LIST after perf 3/n. Verify with IONFLAGS=bl-aot
// that this op emits a callWithABI to a local ABI fn on $JSSHELL_OPT.
// If it does not (fast path or preemptible ABI target), candidates to
// try: Math.abs of a value that forces the negation slow path, or a
// controlled coercion that dispatches to js::ToNumber.

function bench() {
  const INNER = 100_000_000;
  const obj = {};
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    if (typeof obj === "object") {
      n = n + 1;
    }
  }
  return n;
}

const r = bench();
if (r !== 100_000_000) {
  throw new Error("bad abi_call sum: " + r);
}
