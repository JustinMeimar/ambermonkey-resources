#!/usr/bin/env python3
"""Describe one or more selected corpora as typst-ready composition and overlap tables."""

import argparse
import json
import os
import sys
from pathlib import Path

ARTIFACT_KINDS = ("blfun", "ic")
ARTIFACT_SUFFIX = ".aotb"
SINGLETONS = ("interp.aotb", "configuration.aotb")


def die(msg):
    sys.exit(f"corpus_tables: {msg}")


def parse_labelled(pairs, what):
    out = {}
    for pair in pairs:
        label, sep, value = pair.partition("=")
        if not sep or not label:
            die(f"{what} must be LABEL=PATH, got {pair!r}")
        if label in out:
            die(f"duplicate label {label!r}")
        out[label] = Path(value)
    return out


def kind_of(name):
    return name.split("-", 1)[0]


def scan(corpus):
    if not corpus.is_dir():
        die(f"{corpus} is not a directory")
    names = {k: set() for k in ARTIFACT_KINDS}
    sizes = {k: 0 for k in ARTIFACT_KINDS}
    singletons = 0
    for entry in os.scandir(corpus):
        if not entry.name.endswith(ARTIFACT_SUFFIX):
            continue
        if entry.name in SINGLETONS:
            singletons += 1
            continue
        kind = kind_of(entry.name)
        if kind not in names:
            continue
        names[kind].add(entry.name)
        sizes[kind] += entry.stat().st_size
    if not any(names.values()):
        die(f"no {'/'.join(ARTIFACT_KINDS)} artifacts under {corpus}")
    return {"names": names, "sizes": sizes, "singletons": singletons}


def composition(corpora, scans, images):
    columns = ["corpus", "blfun", "blfun_bytes", "ic", "ic_bytes",
               "singletons", "artifact_bytes", "image_bytes"]
    rows = []
    for label, corpus in corpora.items():
        s = scans[label]
        artifact_bytes = sum(s["sizes"].values())
        image = images.get(label)
        if image is not None and not image.is_file():
            die(f"image for {label!r} is not a file: {image}")
        rows.append([
            label,
            len(s["names"]["blfun"]),
            s["sizes"]["blfun"],
            len(s["names"]["ic"]),
            s["sizes"]["ic"],
            s["singletons"],
            artifact_bytes,
            os.path.getsize(image) if image is not None else None,
        ])
    return {"columns": columns, "rows": rows}


def overlap(corpora, scans):
    columns = ["left", "right", "kind", "common", "only_left", "only_right"]
    rows = []
    labels = list(corpora)
    for i, left in enumerate(labels):
        for right in labels[i + 1:]:
            for kind in ARTIFACT_KINDS:
                a = scans[left]["names"][kind]
                b = scans[right]["names"][kind]
                rows.append([left, right, kind,
                             len(a & b), len(a - b), len(b - a)])
    return {"columns": columns, "rows": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", nargs="+", metavar="LABEL=DIR",
                    help="a selected corpus dir under a short label")
    ap.add_argument("--image", action="append", default=[], metavar="LABEL=PATH",
                    help="packed AOTImage.inc produced from the like-labelled corpus")
    args = ap.parse_args()

    corpora = parse_labelled(args.corpus, "corpus")
    images = parse_labelled(args.image, "--image")
    unknown = set(images) - set(corpora)
    if unknown:
        die(f"--image labels with no corpus: {', '.join(sorted(unknown))}")

    scans = {label: scan(path) for label, path in corpora.items()}
    out = {
        "composition": composition(corpora, scans, images),
        "inputs": {label: str(path) for label, path in corpora.items()},
    }
    if len(corpora) > 1:
        out["overlap"] = overlap(corpora, scans)
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
