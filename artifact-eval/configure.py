#!/usr/bin/env python3

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

from install_engines import install, releases

FIREFOX = Path(os.environ.get("AMBERMONKEY_FIREFOX", "/workspace/firefox"))
RESOURCES = Path(os.environ.get("AMBERMONKEY_RESOURCES", "/workspace/ambermonkey-resources"))
ENGINES = Path(os.environ.get("AMBERMONKEY_ENGINES", "/opt/engines"))
RESULTS = Path(os.environ.get("AMBERMONKEY_RESULTS", "/results"))
FOSSIL = os.environ.get("FOSSIL_BIN", "fossil")
FOSSIL_HOME = Path(os.environ.get("FOSSIL_HOME", str(Path.home() / ".fossil")))
SUPPORTED = {
    "7-2-oracle-corpus": "am-browser-release-oracle-sp3",
    "7-2-ambermonkey-perf-s3": "am-browser-release-tp6",
}


def run(command, **kwargs):
    print(f"==> {shlex.join(map(str, command))}", flush=True)
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def configure_fossil(binary=None):
    config = RESOURCES / "fossils/project.toml"
    if not config.is_file():
        raise ValueError(f"resources project missing: {config}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    replacements = {"artifact_dir": str(RESULTS / "artifacts")}
    constants = {"FIREFOX": str(FIREFOX)}
    if binary:
        constants["BIN_AOT"] = str(binary)
        constants["AOT_BROWSER"] = "cd $FIREFOX && $CLEAN_JIT_ENV $NO_CONTENT_SANDBOX_ENV"
    section = ""
    lines = []
    for line in config.read_text().splitlines():
        if line.strip().startswith("["):
            section = line.strip()
        key = line.split("=", 1)[0].strip()
        values = constants if section == "[constants]" else replacements if not section else {}
        lines.append(f"{key} = {json.dumps(values[key])}" if key in values else line)
    config.write_text("\n".join(lines) + "\n")
    projects = FOSSIL_HOME / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    project = projects / "ambermonkey"
    expected = config.parent.resolve()
    if project.is_symlink() and project.resolve() == expected:
        return
    if project.exists() or project.is_symlink():
        raise ValueError(f"{project} already exists and does not point to {expected}")
    project.symlink_to(expected, target_is_directory=True)


def configure_records(name):
    records = RESOURCES / "fossils" / name / "records"
    target = RESULTS / "records" / name
    target.mkdir(parents=True, exist_ok=True)
    if records.is_symlink() and records.resolve() == target.resolve():
        return
    if records.exists() or records.is_symlink():
        raise ValueError(f"existing records directory: {records}; use a clean resources checkout")
    records.symlink_to(target, target_is_directory=True)


def check_raptor():
    if not (FIREFOX / "mach").is_file():
        raise ValueError(f"Firefox/Raptor checkout missing: {FIREFOX}")
    browsertime = FIREFOX / "tools/browsertime/node_modules/browsertime/bin/browsertime.js"
    venv = FIREFOX / "obj-x86_64-pc-linux-gnu/testing/raptor-venv/bin/python"
    if not browsertime.is_file() or not venv.is_file():
        raise ValueError("Raptor dependencies missing; rebuild the Docker image")


def main():
    parser = argparse.ArgumentParser(description="Install engines and configure the evaluation project.")
    parser.add_argument("--release", action="append", choices=list(releases()))
    parser.add_argument("--archives", type=Path, default=Path("/releases"))
    parser.add_argument("--base-url", default=os.environ.get("AMBERMONKEY_RELEASE_URL"))
    parser.add_argument("--register-only", action="store_true", help="register Fossil without installing engines or benchmark dependencies")
    parser.add_argument("--skip-benchmarks", action="store_true", help="skip checking benchmark dependencies")
    args = parser.parse_args()
    binary = None
    if not args.register_only:
        for name in args.release or releases():
            binary = install(name, args.archives, ENGINES, args.base_url)
    print("Registering the Fossil project", flush=True)
    configure_fossil(binary)
    print("Configuring result directories", flush=True)
    for name in SUPPORTED:
        if (RESOURCES / "fossils" / name / "fossil.toml").is_file():
            configure_records(name)
    if not args.register_only and not args.skip_benchmarks:
        print("Checking Raptor dependencies", flush=True)
        check_raptor()
    print("Configuration complete", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"configure: {error}")
