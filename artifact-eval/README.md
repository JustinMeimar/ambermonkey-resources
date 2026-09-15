# AmberMonkey artifact evaluation

The container clones and builds the three repositories that define the
evaluation. It takes the latest `main` from `JustinMeimar/fossil` and
`JustinMeimar/ambermonkey-resources`, and the latest `justin/ambermonkey` from
`JustinMeimar/firefox`.

The mozconfigs and fossil definitions always come from the cloned resources
checkout. The image builds the AOT SpiderMonkey shell using the checked-in
`mozconfigs/shell-release-aot.mozconfig`; the evaluator does not synthesize a
configuration.

Build the image from this directory:

```sh
docker build -t ambermonkey-artifact-eval .
```

The default command runs the dependency-free `0-0-static-tables` fossil. This
is the first integration point: it proves that the cloned Fossil tool discovers
the cloned resources project and writes project artifacts.

```sh
docker run --rm ambermonkey-artifact-eval
```

Pass any Fossil command through the same configured project:

```sh
docker run --rm ambermonkey-artifact-eval fossil list
docker run --rm ambermonkey-artifact-eval fossil bury 7-2-ambermonkey-perf-octane \
  --variant default --iterations 1
```

A local checkout can replace either cloned checkout with a bind mount. This is
for iteration, not the clean evaluator path:

```sh
docker run --rm \
  --mount type=bind,source=/home/justin/spidermonkey/ambermonkey,target=/home/justin/spidermonkey/ambermonkey \
  ambermonkey-artifact-eval static-tables
```

The next increment should make corpus construction an explicit stage, then run
the shell-only Octane fossil. Browser/Raptor fossils, the V8 comparison, and
multi-build indirection measurements can remain later stages.

`ExecutionContext` only supplies a consistent process environment when Fossil
runs a variant, analysis, figure, or table. It helps cloned fossil scripts find
their project and operation, but it does not clone software, build Firefox,
construct corpora, or order evaluation stages; this script and container own
those responsibilities.
