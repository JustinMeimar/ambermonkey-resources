const scriptFile = thisFilename();
const microbenchDir = scriptFile.slice(0, scriptFile.lastIndexOf("/")) +
                      "/../microbenches";

const benchmarks = scriptArgs.length > 0
  ? scriptArgs
  : [
      "interrupt_check",
      "stack_check",
      "prebarrier",
      "vm_call",
      "abi_call",
      "arith",
      "prop_load",
      "array_load",
    ];

for (const benchmark of benchmarks) {
  const path = `${microbenchDir}/${benchmark}.js`;
  printErr(`-- run microbench: ${benchmark}`);
  evaluate(read(path), {
    fileName: path,
    global: newGlobal({newCompartment: true}),
  });
}
