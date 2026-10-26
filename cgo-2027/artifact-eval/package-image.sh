#!/usr/bin/env bash
# Package existing binaries and dependencies without compiling any component.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bash "$here/docker-run.sh" --setup-only --prepare-figures \
    7-3-v8-jitless-comparison 7-5-indirection-overhead
bundle=$(mktemp -d /tmp/amber-image-parent.XXXXXX)/bundle
python3 "$here/prepare_bundle.py" "$bundle"
container=$(docker create \
    --mount "type=bind,src=$bundle,dst=/bundle,readonly" \
    --mount type=volume,src=ambermonkey-artifact-engines,dst=/engine-cache,readonly \
    -e AMBERMONKEY_RESOURCES=/workspace/ambermonkey-resources-current \
    -e AMBERMONKEY_FIREFOX=/workspace/firefox \
    -e AMBERMONKEY_ENGINES=/opt/engines -e AMBERMONKEY_RESULTS=/results \
    -e FOSSIL_HOME=/tmp/fossil-home \
    --entrypoint /bin/sleep \
    "${AMBERMONKEY_BASE_IMAGE:-sha256:39b5fccab5f5506e4cf003fe0268263a0ef79a3dfde40ca6c931db5138441042}" infinity)
trap 'docker rm -f "$container" >/dev/null' EXIT
docker start "$container" >/dev/null
docker exec "$container" python3 /bundle/artifact-eval/install_bundle.py
docker exec "$container" python3 /workspace/artifact-eval-current/run.py --setup-only
docker exec -w /workspace/firefox \
    -e MOZCONFIG=/workspace/ambermonkey-resources-current/artifact-raptor.mozconfig \
    -e AMBERMONKEY_BIN_AOT=/opt/engines/am-browser-release-tp6/firefox/firefox \
    "$container" ./mach python /workspace/artifact-eval-current/run_talos.py --setup-only
docker commit --change 'ENTRYPOINT ["/usr/local/bin/ambermonkey-eval"]' \
    --change 'WORKDIR /workspace/artifact-eval-current' --change 'CMD []' "$container" "${AMBERMONKEY_IMAGE_TAG:-ambermonkey-artifact-eval:smoke}"
