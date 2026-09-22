#=== STEP 1: Download the pinned Firefox source for the Raptor benchmark harness.
FROM rust:1-bookworm AS checkouts
WORKDIR /workspace
ARG FIREFOX_REV=b944ae55957f631191cf6e4337039e5cbea7de42
RUN git init firefox && cd firefox \
    && git remote add origin https://github.com/JustinMeimar/firefox.git \
    && git fetch --depth 1 origin "$FIREFOX_REV" && git checkout --detach FETCH_HEAD

#=== STEP 2: Download the pinned AmberMonkey experiment definitions and scripts.
ARG RESOURCES_REV=3bbbc3742be893c113a8930a13fbf84f91478556
RUN git init ambermonkey-resources && cd ambermonkey-resources \
    && git remote add origin https://github.com/JustinMeimar/ambermonkey-resources.git \
    && git fetch --depth 1 origin "$RESOURCES_REV" && git checkout --detach FETCH_HEAD

#=== STEP 3: Download and build the pinned Fossil research harness.
FROM rust:1-bookworm AS fossil-build
ARG FOSSIL_REV=1bf2cc2b868f9f0171a2cd216a18fae4ba11145e
WORKDIR /src/fossil
RUN git init . && git remote add origin https://github.com/JustinMeimar/fossil.git \
    && git fetch --depth 1 origin "$FOSSIL_REV" && git checkout --detach FETCH_HEAD
RUN cargo install --locked --path . --root /opt/fossil

#=== STEP 4: Create the Ubuntu container and install browser and benchmark dependencies.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --yes --no-install-recommends \
    ca-certificates curl git python3 python3-venv python3-pip python3-numpy \
    python3-matplotlib sudo xz-utils zstd unzip ffmpeg \
    libgtk-3-0t64 libdbus-glib-1-2 libasound2t64 libx11-xcb1 libxt6t64 \
    libnss3 libgbm1 libpci3 binutils \
    && rm -rf /var/lib/apt/lists/*
# Install Node 22 and npm from the official Node image so Raptor finds them on PATH.
COPY --from=node:22-bookworm-slim /usr/local/ /usr/local/

#=== STEP 5: Install Fossil and copy the cached source checkouts into the container.
COPY --from=fossil-build /opt/fossil/bin/fossil /usr/local/bin/fossil

WORKDIR /workspace
COPY --from=checkouts /workspace/firefox /workspace/firefox
COPY --from=checkouts /workspace/ambermonkey-resources /workspace/ambermonkey-resources

#=== STEP 6: Install Browsertime, its drivers and FFmpeg, and Raptor's Python dependencies.
ENV MOZBUILD_STATE_PATH=/root/.mozbuild
WORKDIR /workspace/firefox
RUN python3 mach browsertime --setup
COPY prepare_raptor.py /workspace/artifact-eval/prepare_raptor.py
RUN python3 mach python /workspace/artifact-eval/prepare_raptor.py

#=== STEP 7: Copy setup, the release installer, the evaluation runner, and checksums.
COPY configure.py artifact_eval.py install_engines.py releases.json /workspace/artifact-eval/

#=== STEP 8: Set paths for the harness, installed engines, and evaluation results.
ENV FOSSIL_HOME=/root/.fossil \
    AMBERMONKEY_FIREFOX=/workspace/firefox \
    AMBERMONKEY_RESOURCES=/workspace/ambermonkey-resources \
    AMBERMONKEY_ENGINES=/opt/engines \
    AMBERMONKEY_RESULTS=/results
WORKDIR /workspace/artifact-eval

#=== STEP 9: Register Fossil without running experiments.
RUN python3 configure.py --register-only

#=== STEP 10: Open a shell so releases and experiments can be invoked manually.
CMD ["/bin/bash"]
