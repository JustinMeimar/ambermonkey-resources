# AmberMonkey (CGO 2027) artifact image. Engines come prebuilt from releases/;
# the only thing compiled here is the Fossil benchmark harness.

#=== Fossil benchmark harness, pinned.
FROM rust:1-bookworm AS fossil
ARG FOSSIL_REV=e4834df886cc0bb6a580b35e2231a6e69317cbb7
RUN cargo install --locked --root /opt/fossil \
    --git https://github.com/JustinMeimar/fossil.git --rev "$FOSSIL_REV" fossil

#=== Experiment definitions (fossils-I), pinned.
FROM alpine/git:v2.47.2 AS resources-checkout
ARG RESOURCES_REV=ed47851563e034254e922cf7e928f0e89c4e24e9
RUN git init /src && cd /src \
    && git remote add origin https://github.com/JustinMeimar/ambermonkey-resources.git \
    && git fetch --depth 1 origin "$RESOURCES_REV" && git checkout --detach FETCH_HEAD
FROM scratch AS resources
COPY --from=resources-checkout /src/fossils-I /fossils-I

#=== Firefox source at the AmberMonkey revision: provides mach raptor/talos and Octane.
FROM alpine/git:v2.47.2 AS firefox
ARG FIREFOX_REV=b944ae55957f631191cf6e4337039e5cbea7de42
RUN git init /firefox && cd /firefox \
    && git remote add origin https://github.com/JustinMeimar/firefox.git \
    && git fetch --depth 1 origin "$FIREFOX_REV" && git checkout --detach FETCH_HEAD \
    && rm -rf .git

#=== Verify and unpack the prebuilt engines in releases/.
FROM ubuntu:24.04 AS engines
RUN apt-get update && apt-get install --yes --no-install-recommends python3 xz-utils zstd \
    && rm -rf /var/lib/apt/lists/*
COPY releases.json install_releases.py /tmp/
COPY releases/ /tmp/releases/
RUN python3 /tmp/install_releases.py /tmp/releases /opt/engines

#=== Evaluation image.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --yes --no-install-recommends \
    ca-certificates curl git python3 python3-venv python3-pip xz-utils zstd unzip ffmpeg binutils \
    libgtk-3-0t64 libdbus-glib-1-2 libasound2t64 libx11-xcb1 libxt6t64 libnss3 libgbm1 libpci3 \
    libatk-bridge2.0-0t64 libcups2t64 libxkbcommon0 libdrm2 libxshmfence1 \
    linux-tools-generic \
    && ln -s "$(ls -d /usr/lib/linux-tools/*-generic | tail -1)/perf" /usr/local/bin/perf \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node:22-bookworm-slim /usr/local/ /usr/local/
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv
COPY --from=fossil /opt/fossil/bin/fossil /usr/local/bin/fossil
COPY --from=firefox /firefox /workspace/firefox

# Raptor (browsertime + its virtualenv) and Talos, run against prebuilt browsers.
ENV MOZBUILD_STATE_PATH=/root/.mozbuild \
    AMBERMONKEY_FIREFOX=/workspace/firefox \
    AMBERMONKEY_MOZCONFIG_AOT=/workspace/raptor.mozconfig \
    AMBERMONKEY_MOZCONFIG_RELEASE=/workspace/raptor.mozconfig \
    MOZCONFIG=/workspace/raptor.mozconfig
RUN echo 'mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-x86_64-pc-linux-gnu' > /workspace/raptor.mozconfig
WORKDIR /workspace/firefox
RUN ./mach browsertime --setup
COPY prepare_raptor.py run_talos.py /workspace/artifact-eval/
RUN ./mach python /workspace/artifact-eval/prepare_raptor.py

COPY --from=engines /opt/engines /opt/engines
ENV AMBERMONKEY_BIN_RELEASE=/opt/engines/default-browser-release/dist/bin/firefox \
    AMBERMONKEY_BIN_AOT=/opt/engines/am-browser-release-tp6/dist/bin/firefox \
    AMBERMONKEY_JSSHELL_RIT=/opt/engines/indirection-rit-candidate/js \
    AMBERMONKEY_JSSHELL_NATIVE_LINKER=/opt/engines/indirection-native-linker-candidate/js \
    AMBERMONKEY_JSSHELL_NATIVE_LINKER_VALUE_MIRROR=/opt/engines/indirection-native-linker-value-mirror-candidate/js \
    AMBERMONKEY_V8=/opt/v8-project \
    AMBERMONKEY_TALOS_LAUNCHER=/workspace/artifact-eval/run_talos.py \
    AMBERMONKEY_RELEASE_MANIFEST=/workspace/artifact-eval/releases.json
RUN ./mach python /workspace/artifact-eval/run_talos.py --setup-only
# 7-3 launches Chromium and ChromeDriver through these wrappers.
RUN mkdir /opt/v8-project \
    && printf '#!/bin/sh\nexec /opt/engines/chromium-no-pgo/chromium/Default/chrome --no-sandbox "$@"\n' \
       > /opt/v8-project/run-chromium-nixos.sh \
    && printf '#!/bin/sh\nexec /opt/engines/chromedriver-155/chromedriver-linux64/chromedriver "$@"\n' \
       > /opt/v8-project/run-chromedriver-nixos.sh \
    && chmod +x /opt/v8-project/*.sh

# Experiment definitions, their locked figure dependencies, and Fossil registration.
COPY --from=resources /fossils-I /workspace/fossils-I
RUN uv export --project /workspace/fossils-I --locked --no-dev --no-hashes --format requirements-txt \
       > /tmp/requirements.txt \
    && uv pip install --system --break-system-packages --no-build -r /tmp/requirements.txt \
    && mkdir -p /root/.fossil/projects \
    && ln -s /workspace/fossils-I /root/.fossil/projects/ambermonkey-cgo

COPY evaluation.json releases.json run.py README.md /workspace/artifact-eval/
WORKDIR /workspace/artifact-eval
ENTRYPOINT ["python3", "/workspace/artifact-eval/run.py"]
