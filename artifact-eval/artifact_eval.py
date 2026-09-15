#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
FIREFOX_SOURCE = Path(os.environ.get("FIREFOX_SOURCE", "/work/firefox")).resolve()
EVAL_ROOT = Path(
    os.environ.get("ARTIFACT_EVAL_WORK_DIR", "/work/evaluation")
).resolve()
OBJDIR = EVAL_ROOT / "obj"
CORPUS_DIR = EVAL_ROOT / "corpus"
BUNDLE_DIR = EVAL_ROOT / "bundle"
MOZCONFIG_PATH = EVAL_ROOT / "mozconfig"
WORKLOAD = SCRIPT_DIR / "smoke.js"
EXPECTED_OUTPUT = "ambermonkey-smoke: 49995000"
WORK_ROOT_MARKER = EVAL_ROOT / ".ambermonkey-artifact-eval"


def write_mozconfig() -> None:
    if EVAL_ROOT.exists() and not WORK_ROOT_MARKER.exists() and any(EVAL_ROOT.iterdir()):
        sys.exit(
            "artifact-eval: refusing to use a non-empty, unrecognized work directory: "
            f"{EVAL_ROOT}"
        )
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    WORK_ROOT_MARKER.touch()
    MOZCONFIG_PATH.write_text(
        "\n".join(
            (
                "ac_add_options --enable-application=js",
                "ac_add_options --enable-optimize",
                "ac_add_options --enable-aot",
                "ac_add_options --disable-debug",
                "ac_add_options --disable-tests",
                f"mk_add_options MOZ_OBJDIR={OBJDIR}",
                "mk_add_options AUTOCLOBBER=1",
                "",
            )
        )
    )


def mach(*args: str) -> None:
    environment = os.environ.copy()
    environment["MOZCONFIG"] = str(MOZCONFIG_PATH)
    subprocess.run(
        [str(FIREFOX_SOURCE / "mach"), *args],
        cwd=FIREFOX_SOURCE,
        env=environment,
        check=True,
    )


def build() -> None:
    print("==> Building the empty-image AOT JavaScript shell", flush=True)
    mach("build")


def evaluate() -> None:
    shell = OBJDIR / "dist/bin/js"
    if not shell.is_file():
        sys.exit("artifact-eval: no stage-1 shell; run 'artifact_eval.py build' first")

    # These directories are wholly owned by this program and deliberately
    # replaced so repeated evaluations cannot consume stale artifacts.
    shutil.rmtree(CORPUS_DIR, ignore_errors=True)
    shutil.rmtree(BUNDLE_DIR, ignore_errors=True)

    print("==> Recording a deterministic smoke workload", flush=True)
    mach(
        "ambermonkey",
        "record",
        "--corpus",
        str(CORPUS_DIR),
        "--workload",
        str(WORKLOAD),
    )

    print("==> Packing the corpus and relinking the shell", flush=True)
    mach(
        "ambermonkey",
        "build-image",
        "--corpus",
        str(CORPUS_DIR),
        "--output-dir",
        str(BUNDLE_DIR),
    )

    print("==> Inspecting the packed image", flush=True)
    mach(
        "ambermonkey",
        "show-image",
        "--image",
        str(OBJDIR / "js/src/jit/aot/AOTImage.inc"),
        "--limit",
        "0",
    )

    print("==> Running strictly from the AOT image", flush=True)
    completed = subprocess.run(
        [
            str(BUNDLE_DIR / "js"),
            "--aot",
            "--aot-only",
            "--aot-enforce",
            "--no-ion",
            "--no-native-regexp",
            "-f",
            str(WORKLOAD),
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    output = completed.stdout.strip()
    print(output)
    if output != EXPECTED_OUTPUT:
        sys.exit(f"artifact-eval: expected {EXPECTED_OUTPUT!r}, got {output!r}")

    print("==> AmberMonkey artifact smoke evaluation passed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and exercise the smallest AmberMonkey artifact pipeline."
    )
    parser.add_argument(
        "action",
        choices=("all", "build", "evaluate"),
        default="all",
        nargs="?",
    )
    args = parser.parse_args()

    mach_path = FIREFOX_SOURCE / "mach"
    if not mach_path.is_file():
        sys.exit(f"artifact-eval: FIREFOX_SOURCE does not contain mach: {FIREFOX_SOURCE}")

    write_mozconfig()
    if args.action in ("all", "build"):
        build()
    if args.action in ("all", "evaluate"):
        evaluate()


if __name__ == "__main__":
    main()
