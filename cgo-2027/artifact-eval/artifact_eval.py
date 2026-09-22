#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import tomllib

import configure as setup


def fossil(*arguments):
    if not shutil.which(setup.FOSSIL):
        raise ValueError(f"Fossil executable missing: {setup.FOSSIL}")
    setup.run([setup.FOSSIL, "--home", setup.FOSSIL_HOME, "--project", "ambermonkey", *arguments])


def definitions():
    return {path.parent.name: tomllib.loads(path.read_text())
            for path in sorted((setup.RESOURCES / "fossils").glob("*/fossil.toml"))}


def main():
    parser = argparse.ArgumentParser(description="Run configured fossils sequentially and wait for completion.")
    parser.add_argument("names", nargs="*", help="fossils to run; default: all supported fossils")
    parser.add_argument("--iterations", type=int, default=int(os.environ.get("N", "1")))
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.iterations < 1:
        raise ValueError("iterations must be positive")
    available = definitions()
    if not available:
        raise ValueError("no fossils found; run configure.py first")
    names = args.names or [name for name in available if name in setup.SUPPORTED or name == "0-0-static-tables"]
    binaries = {}
    for name in names:
        if name not in available:
            raise ValueError(f"unknown fossil: {name}")
        if name == "0-0-static-tables":
            if args.variant:
                raise ValueError("static tables have no variants")
            continue
        if name not in setup.SUPPORTED:
            raise ValueError(f"prerequisites not configured for {name}")
        supported = setup.VARIANTS.get(name, available[name].get("variants", {}).keys())
        unknown = set(args.variant) - set(supported)
        if unknown:
            raise ValueError(f"unavailable variants for {name}: {', '.join(sorted(unknown))}")
        release = setup.SUPPORTED[name]
        binary = setup.executable(release)
        if not binary.is_file():
            raise ValueError(f"engine missing: {binary}; run configure.py first")
        binaries[name] = binary
        if name == "7-6-binary-size" and not setup.executable("default-browser-release").is_file():
            raise ValueError("default browser missing; run configure.py first")
        if name == "7-2-ambermonkey-perf-octane" and not (setup.FIREFOX / "js/src/octane/base.js").is_file():
            raise ValueError("Octane benchmark missing from the Firefox checkout")
    if not (setup.FOSSIL_HOME / "projects/ambermonkey/project.toml").is_file():
        raise ValueError("Fossil project missing; run configure.py first")
    browser_fossils = set(binaries) - {"7-2-ambermonkey-perf-octane", "7-6-binary-size"}
    if browser_fossils and not (setup.FIREFOX / "mach").is_file():
        raise ValueError(f"Firefox/Raptor checkout missing: {setup.FIREFOX}")
    if browser_fossils and not args.dry_run:
        setup.check_raptor()
    if not args.names:
        for name in sorted(available.keys() - set(names)):
            print(f"Skipping {name}: prerequisites not configured", flush=True)
    for name in names:
        if name == "0-0-static-tables":
            if not args.dry_run:
                for table in available[name].get("tables", {}):
                    fossil("table", name, "--table", table)
            continue
        setup.configure_fossil(binaries[name])
        if not available[name].get("variants"):
            for table in setup.TABLES.get(name, available[name].get("tables", {})):
                if args.dry_run:
                    print(f"Would render {name}: {table}", flush=True)
                else:
                    fossil("table", name, "--table", table)
            continue
        selected = args.variant or list(setup.VARIANTS.get(name, available[name]["variants"]))
        command = ["bury", name, "--iterations", str(args.iterations)]
        for variant in selected:
            command.extend(["--variant", variant])
        if args.dry_run:
            fossil(*command, "--dry-run")
            continue
        fossil(*command)
        fossil("analyze", *[f"{name}:{variant}" for variant in selected], "--last", "1")
        for kind, flag in (("tables", "table"), ("figures", "figure")):
            outputs = setup.TABLES if kind == "tables" else setup.FIGURES
            for output in outputs.get(name, available[name].get(kind, {})):
                if name == "7-2-oracle-corpus" and output != "speedometer3":
                    continue
                fossil(flag, name, f"--{flag}", output, "--last", str(len(selected)))
        if name == "7-2-ambermonkey-perf-octane":
            print("Octane recorded and analyzed; full tier figures need the AmberMonkey shell and interpreter baseline", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"artifact-eval: {error}")
