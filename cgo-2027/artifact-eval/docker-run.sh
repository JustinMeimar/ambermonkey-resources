#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
resources=$(cd "$here/../.." && pwd)
fossil_bin=$(command -v fossil)
uv_bin=$(command -v uv)
results=${AMBERMONKEY_RESULTS_HOST:-"$here/../artifact-smoke-results"}
mkdir -p "$results"
entrypoint=run.py
if [[ "${1:-}" == --suite ]]; then
    entrypoint=smoke.py
    shift
fi
extra=()
# The existing host Fossil is linked against Nix libraries. Reuse it without a build.
if [[ -d /nix/store ]]; then
    extra+=(--mount type=bind,src=/nix/store,dst=/nix/store,readonly)
fi
if [[ " $* " == *" 7-5-indirection-overhead "* ]]; then
    perf_bin=$(command -v perf)
    extra+=(--cap-add PERFMON --mount "type=bind,src=$perf_bin,dst=/usr/local/bin/perf,readonly")

fi
exec docker run --rm --init --shm-size=2g \
    "${extra[@]}" \
    --mount "type=bind,src=$resources,dst=/input,readonly" \
    --mount "type=bind,src=$resources/cgo-2027/releases,dst=/releases,readonly" \
    --mount "type=bind,src=$fossil_bin,dst=/usr/local/bin/fossil,readonly" \
    --mount "type=bind,src=$uv_bin,dst=/usr/local/bin/uv,readonly" \
    --mount "type=bind,src=$results,dst=/results" \
    --mount type=volume,src=ambermonkey-artifact-engines,dst=/opt/engines \
    -e AMBERMONKEY_RESOURCES=/tmp/ambermonkey-resources \
    -e AMBERMONKEY_FIREFOX=/workspace/firefox \
    -e AMBERMONKEY_ENGINES=/opt/engines -e AMBERMONKEY_RESULTS=/results \
    -e FOSSIL_HOME=/tmp/fossil-home \
    --entrypoint python3 "${AMBERMONKEY_DOCKER_IMAGE:-am-artifact-eval:latest}" \
    "/input/cgo-2027/artifact-eval/$entrypoint" "$@"
