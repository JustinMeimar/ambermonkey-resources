# AmberMonkey artifact evaluation

This is the smallest end-to-end evaluation of AmberMonkey's artifact path. It
builds an AOT-enabled SpiderMonkey shell with an empty image, records a small
deterministic workload, packs and relinks the image, then runs the bundled shell
with runtime JIT compilation prohibited.

It intentionally does not run a paper fossil yet. Even the simplest empirical
paper fossils require a preselected corpus, multiple configurations, browser
automation, or multiple builds. This smoke evaluation isolates the mechanism
those experiments depend on.

## Pinned container evaluation

From this directory:

```sh
docker build -t am-artifact-eval .
docker run --rm am-artifact-eval
```

The image clones the public AmberMonkey repository at the immutable revision
specified by `FIREFOX_REVISION`, bootstraps the SpiderMonkey toolchain, and
builds the stage-1 shell. `docker run` performs the record, pack, relink, and
execution steps. Override the source only deliberately:

```sh
docker build \
  --build-arg FIREFOX_REVISION=<full-commit-id> \
  -t ambermonkey-artifact-eval .
```

## Iterate on a local Firefox checkout

You can point the already-built image at local source with a read-only bind
mount. The build output remains in the container and does not reuse host
binaries:

```sh
docker run --rm \
  --mount type=bind,source=/home/justin/spidermonkey/firefox,target=/work/firefox,readonly \
  ambermonkey-artifact-eval all
```

This is convenient, but its input is whatever is in the local checkout and is
therefore not the reproducible evaluator path. Reusing a host objdir would also
couple the evaluation to host libraries and absolute paths.

For repeated local builds, preserve only the container-built work directory:

```sh
docker volume create ambermonkey-eval-work
docker run --rm \
  --mount type=bind,source=/home/justin/spidermonkey/firefox,target=/work/firefox,readonly \
  --mount type=volume,source=ambermonkey-eval-work,target=/work/evaluation \
  ambermonkey-artifact-eval all
```

## What remains before the paper fossils are reproducible

The current fossil project configuration contains host-specific Firefox build
paths and shared corpus paths. Fossil records commands and routes their process
environment, but it does not acquire source, build configurations, construct a
corpus, or describe dependencies between those stages. Browser fossils also
need Raptor's downloaded test assets and substantially more runtime.

The next useful increment is a shell-only Octane evaluation using a corpus
built inside this same container. Browser/Raptor fossils, V8 comparison, and
the multi-build indirection experiment should follow after that dependency is
explicit.
