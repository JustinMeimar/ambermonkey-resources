#!/usr/bin/env bash
# Build the artifact image (cached after the first time) and run the evaluation.
# Arguments go to run.py: --list, --only EXPERIMENT, -n N, --resume RUN.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
docker build -t ambermonkey-artifact .
mkdir -p results
# PERFMON lets 7-5-indirection-overhead read hardware counters inside the container.
exec docker run --rm --init --shm-size=2g --cap-add PERFMON \
    --mount "type=bind,src=$PWD/results,dst=/results" \
    ambermonkey-artifact "$@"
