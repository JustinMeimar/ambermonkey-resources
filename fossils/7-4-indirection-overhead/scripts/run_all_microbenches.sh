#!/usr/bin/env bash

set -u -o pipefail

if (( $# < 1 )); then
  echo "usage: $0 JSSHELL [JSSHELL_FLAGS ...]" >&2
  exit 2
fi

js_shell=$1
shift
js_flags=("$@")
fossil_dir=/home/justin/spidermonkey/ambermonkey/fossils/7-4-indirection-overhead

benchmarks=(
  "interrupt-check|$fossil_dir/microbenches/interrupt_check.js"
  "stack-check|$fossil_dir/microbenches/stack_check.js"
  "prebarrier|$fossil_dir/microbenches/prebarrier.js"
  "vm-call|$fossil_dir/microbenches/vm_call.js"
  "abi-call|$fossil_dir/microbenches/abi_call.js"
)

for specification in "${benchmarks[@]}"; do
  IFS="|" read -r bench bench_path <<< "$specification"
  perf_output=$(mktemp /tmp/amber-7-4.XXXXXX.json)

  printf '# benchmark=%s\n' "$bench"
  perf stat \
    --output="$perf_output" \
    -j \
    -e cycles:u,instructions:u,ref-cycles:u \
    "$js_shell" "${js_flags[@]}" -f "$bench_path" 1>&2
  status=$?

  cat "$perf_output"
  rm -f "$perf_output"
  if (( status != 0 )); then
    exit "$status"
  fi
done
