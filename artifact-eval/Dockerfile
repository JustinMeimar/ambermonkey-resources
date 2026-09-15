FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl \
        git \
        python3 \
        sudo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 justin \
    && echo 'justin ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/justin \
    && install -d -o justin -g justin \
        /home/justin/tools \
        /home/justin/spidermonkey

USER justin
WORKDIR /home/justin

RUN git clone --depth 1 \
        https://github.com/JustinMeimar/ambermonkey-resources.git \
        /home/justin/spidermonkey/ambermonkey \
    && git clone --depth 1 \
        https://github.com/JustinMeimar/fossil.git \
        /home/justin/tools/fossil \
    && git clone --depth 1 --branch justin/ambermonkey \
        https://github.com/JustinMeimar/firefox.git \
        /home/justin/spidermonkey/firefox

WORKDIR /home/justin/spidermonkey/firefox
RUN ./mach --no-interactive bootstrap --application-choice js

ENV PATH=/home/justin/.cargo/bin:$PATH
WORKDIR /home/justin/tools/fossil
RUN cargo build --release --locked

WORKDIR /home/justin/spidermonkey/firefox
RUN MOZCONFIG=/home/justin/spidermonkey/ambermonkey/mozconfigs/shell-release-aot.mozconfig \
    ./mach build

COPY --chown=justin:justin artifact_eval.py /usr/local/bin/artifact-eval

WORKDIR /home/justin/spidermonkey/ambermonkey
ENTRYPOINT ["python3", "/usr/local/bin/artifact-eval"]
CMD ["static-tables"]
