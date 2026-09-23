// JSOp::Debugger unconditionally emits callVM<OnDebuggerStatement>. With no
// debugger attached, the VM helper only tests whether the realm is a debuggee
// and returns true. This exercises one VM-wrapper call per iteration without
// allocation, GC, or unrelated object enumeration.

function bench() {
  const INNER = 100_000_000;
  let n = 0;
  for (let i = 0; i < INNER; i++) {
    debugger;
    n = n + 1;
  }
  return n;
}

const r = bench();
if (r !== 100_000_000) {
  throw new Error("bad vm_call sum: " + r);
}
