#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


FIREFOX = Path(
    os.environ.get("AMBERMONKEY_FIREFOX", "/home/justin/spidermonkey/firefox")
)
RESOURCES = Path(
    os.environ.get("AMBERMONKEY_RESOURCES", "/home/justin/spidermonkey/ambermonkey")
)
FOSSIL = Path(
    os.environ.get("FOSSIL_BIN", "/home/justin/tools/fossil/target/release/fossil")
)
FOSSIL_HOME = Path(os.environ.get("FOSSIL_HOME", "/home/justin/.fossil"))


def run(command: list[str], **kwargs) -> None:
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, check=True, **kwargs)


def require_checkout(path: Path, description: str) -> None:
    if not path.is_dir():
        sys.exit(f"artifact-eval: {description} checkout not found: {path}")


def configure_fossil() -> None:
    projects = FOSSIL_HOME / "projects"
    project = projects / "ambermonkey"
    projects.mkdir(parents=True, exist_ok=True)

    expected = RESOURCES / "fossils"
    if project.is_symlink() and project.resolve() == expected.resolve():
        return
    if project.exists() or project.is_symlink():
        sys.exit(f"artifact-eval: {project} exists and does not point to {expected}")
    project.symlink_to(expected, target_is_directory=True)


def fossil(*arguments: str) -> None:
    run(
        [
            str(FOSSIL),
            "--home",
            str(FOSSIL_HOME),
            "--project",
            "ambermonkey",
            *arguments,
        ]
    )


def build_shell() -> None:
    environment = os.environ.copy()
    environment["MOZCONFIG"] = str(
        RESOURCES / "mozconfigs" / "shell-release-aot.mozconfig"
    )
    run([str(FIREFOX / "mach"), "build"], cwd=FIREFOX, env=environment)


def static_tables() -> None:
    fossil("table", "0-0-static-tables", "--table", "runtime-dependencies")
    fossil("table", "0-0-static-tables", "--table", "execution-configurations")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build AmberMonkey and run its Fossil evaluations."
    )
    subcommands = parser.add_subparsers(dest="action", required=True)
    subcommands.add_parser("build", help="build the AOT SpiderMonkey shell")
    subcommands.add_parser(
        "static-tables", help="run the simplest, dependency-free fossil"
    )
    fossil_parser = subcommands.add_parser(
        "fossil", help="pass the remaining arguments directly to Fossil"
    )
    fossil_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_checkout(FIREFOX, "AmberMonkey Firefox")
    require_checkout(RESOURCES, "AmberMonkey resources")
    if not FOSSIL.is_file():
        sys.exit(f"artifact-eval: Fossil executable not found: {FOSSIL}")
    configure_fossil()

    if args.action == "build":
        build_shell()
    elif args.action == "static-tables":
        static_tables()
    elif args.action == "fossil":
        if not args.arguments:
            sys.exit("artifact-eval: fossil requires a Fossil command")
        fossil(*args.arguments)


if __name__ == "__main__":
    main()
