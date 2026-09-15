# syntax=docker/dockerfile:1.7

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


# What is the point of this?
ENV MOZBUILD_STATE_PATH=/home/evaluator/.mozbuild

ARG FIREFOX_REPOSITORY=https://github.com/JustinMeimar/firefox.git
ARG FIREFOX_REVISION=b944ae55957f631191cf6e4337039e5cbea7de42
RUN git clone --filter=blob:none --no-checkout "${FIREFOX_REPOSITORY}" /work/firefox \
    && cd /work/firefox \
    && git fetch --depth=1 origin "${FIREFOX_REVISION}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${FIREFOX_REVISION}"

WORKDIR /work/firefox
RUN ./mach --no-interactive bootstrap --application-choice js

COPY --chown=evaluator:evaluator artifact_eval.py smoke.js /opt/artifact-eval/

ENV FIREFOX_SOURCE=/work/firefox
ENV ARTIFACT_EVAL_WORK_DIR=/work/evaluation

# Build the stage-1, empty-image shell into the image. Running the container
# performs the much shorter record -> pack -> relink -> execute evaluation.
RUN python3 /opt/artifact-eval/artifact_eval.py build

ENTRYPOINT ["python3", "/opt/artifact-eval/artifact_eval.py"]
CMD ["evaluate"]
