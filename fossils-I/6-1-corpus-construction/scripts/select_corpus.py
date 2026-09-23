#!/usr/bin/env python3
"""Stage a corpus dir from per-site recordings: union over the listed training sites.

configuration.aotb must be byte-identical across sites (JitOptions fingerprint).
interp.aotb accepts a majority pick with a warning. --self-hosted overlays a
shell --aot-record-self-hosted dir; its baselines are always kept."""

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

STRICT_SINGLETONS = ("configuration.aotb",)
LOOSE_SINGLETONS = ("interp.aotb",)
ARTIFACT_KINDS = ("blfun", "ic")
SELF_HOSTED_KIND = "blfun"
ARTIFACT_SUFFIX = ".aotb"
LINK_MODES = ("copy", "symlink", "hardlink")


def die(msg):
    sys.exit(f"select_corpus: {msg}")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def place(src, dst, mode):
    if mode == "copy":
        shutil.copy2(src, dst)
    elif mode == "symlink":
        os.symlink(src.resolve(), dst)
    elif mode == "hardlink":
        os.link(src, dst)
    else:
        raise ValueError(f"unknown link mode: {mode}")


def kind_of(name):
    return name.split("-", 1)[0]


def is_artifact(name, kinds):
    return name.endswith(ARTIFACT_SUFFIX) and kind_of(name) in kinds


def read_sites_file(path):
    names = []
    for raw in path.read_text().splitlines():
        s = raw.split("#", 1)[0].strip()
        if s:
            names.append(s)
    if not names:
        die(f"{path} lists no sites")
    seen = set()
    for n in names:
        if n in seen:
            die(f"{path}: duplicate entry {n!r}")
        seen.add(n)
    return names


def resolve_site_dirs(root, listed):
    dirs = []
    missing = []
    for name in listed:
        p = root / name
        if not p.is_dir():
            missing.append(name)
            continue
        dirs.append(p)
    if missing:
        die(f"{root}: listed sites without a per-site subdir: {', '.join(missing)}")
    return dirs


def index_artifacts(sites, kinds):
    index = {}
    for site in sites:
        for f in site.iterdir():
            if not is_artifact(f.name, kinds):
                continue
            entry = index.get(f.name)
            if entry is None:
                index[f.name] = {"sites": [site.name], "size": f.stat().st_size, "src": f}
            else:
                entry["sites"].append(site.name)
    return index


def pick_singletons(sites):
    picks = {}
    notes = []
    for name in STRICT_SINGLETONS:
        candidates = [s / name for s in sites if (s / name).exists()]
        if not candidates:
            die(f"no site produced {name}")
        digests = {digest(c) for c in candidates}
        if len(digests) > 1:
            die(
                f"{name} differs across sites "
                f"({len(digests)} distinct digests) -- build mismatch"
            )
        picks[name] = candidates[0]
    for name in LOOSE_SINGLETONS:
        candidates = [s / name for s in sites if (s / name).exists()]
        if not candidates:
            die(f"no site produced {name}")
        buckets = {}
        for c in candidates:
            buckets.setdefault(digest(c), []).append(c)
        if len(buckets) > 1:
            sizes = sorted(((len(v), k) for k, v in buckets.items()), reverse=True)
            notes.append(
                f"{name}: {len(buckets)} distinct digests across {len(candidates)} sites "
                f"(sizes={[n for n, _ in sizes]}); picking majority"
            )
        majority_digest = max(buckets, key=lambda k: len(buckets[k]))
        picks[name] = buckets[majority_digest][0]
    return picks, notes


def overlay_self_hosted(src, config, output, mode):
    if not src.is_dir():
        die(f"{src} is not a directory")
    theirs = src / "configuration.aotb"
    if not theirs.exists():
        die(f"{src} has no configuration.aotb")
    if digest(theirs) != digest(config):
        die(
            "self-hosted configuration.aotb differs from the per-site one; "
            "the two recordings disagree on build or JitOptions and their "
            "blobs cannot be packed together"
        )
    picked, picked_bytes = 0, 0
    for f in sorted(src.iterdir()):
        if not is_artifact(f.name, frozenset({SELF_HOSTED_KIND})):
            continue
        place(f, output / f.name, mode)
        picked += 1
        picked_bytes += f.stat().st_size
    if not picked:
        die(f"no {SELF_HOSTED_KIND}- artifacts under {src}")
    return {"self_hosted_input": str(src),
            "self_hosted_picked": picked,
            "self_hosted_bytes": picked_bytes}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="dir containing per-site subdirs")
    ap.add_argument("output", type=Path, help="corpus dir to create")
    ap.add_argument("--sites", type=Path, required=True,
                    help="text file listing the sites to union, one name per line")
    ap.add_argument("--exclude-kind", action="append", choices=ARTIFACT_KINDS,
                    default=[], metavar="KIND",
                    help=f"drop an artifact kind from the per-site index; repeatable "
                         f"(choices: {', '.join(ARTIFACT_KINDS)})")
    ap.add_argument("--self-hosted", type=Path, default=None,
                    help="dir from a shell --aot-record --aot-record-self-hosted run; "
                         "its baseline functions are copied in whole, exempt from "
                         "--exclude-kind")
    ap.add_argument("--force", action="store_true",
                    help="overwrite output dir if it exists")
    ap.add_argument("--mode", choices=LINK_MODES, default="copy",
                    help="how to place picked artifacts into OUTPUT (default: copy)")
    args = ap.parse_args()

    kinds = frozenset(ARTIFACT_KINDS) - frozenset(args.exclude_kind)
    if not kinds and not args.self_hosted:
        die("every artifact kind excluded and no --self-hosted dir")

    if args.output.exists():
        if not args.force:
            die(f"{args.output} exists (pass --force to overwrite)")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    listed = read_sites_file(args.sites)
    sites = resolve_site_dirs(args.input, listed)

    singletons, notes = pick_singletons(sites)
    for name, src in singletons.items():
        place(src, args.output / name, args.mode)

    index = index_artifacts(sites, kinds)
    picked_bytes = 0
    for name, meta in index.items():
        place(meta["src"], args.output / name, args.mode)
        picked_bytes += meta["size"]

    summary = {
        "sites_listed": len(listed),
        "sites_indexed": len(sites),
        "kinds_included": sorted(kinds),
        "kinds_excluded": sorted(set(args.exclude_kind)),
        "artifacts_picked": len(index),
        "bytes_picked": picked_bytes,
        "singletons": sorted(singletons),
        "singleton_notes": notes,
        "mode": args.mode,
        "output": str(args.output),
        "sites_file": str(args.sites),
    }
    if args.self_hosted:
        summary.update(overlay_self_hosted(
            args.self_hosted, singletons["configuration.aotb"], args.output, args.mode
        ))
    import json
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
