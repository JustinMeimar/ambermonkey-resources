#!/usr/bin/env python3

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


TESTS = {
    "speedometer3": ("speedometer3", 1),
    "jetstream3": ("jetstream3", 1),
    "tp6": ("browsertime-tp6", 2),
}


def emit(item):
    print(json.dumps(item, ensure_ascii=True), flush=True)


def main():
    benchmark = sys.argv[1]
    test, page_cycles = TESTS[benchmark]
    project = Path(os.environ["FOSSIL_PROJECT_DIR"])
    firefox = project.parent.parent / "firefox"
    browser = firefox / "build-browser-release/dist/bin/firefox"
    parser_path = firefox / "js/src/jit/baseline_cache_trace.py"
    spec = importlib.util.spec_from_file_location("baseline_cache_trace", parser_path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    with tempfile.TemporaryDirectory(prefix="baseline-cache-") as directory:
        log_base = Path(directory) / "trace"
        command = [
            "./mach", "raptor", "-t", test, "--app", "firefox",
            "--binary", str(browser), "--browser-cycles", "1",
            "--page-cycles", str(page_cycles),
            "--setenv", "MOZ_LOG=baselineCache:4",
            "--setenv", f"MOZ_LOG_FILE={log_base}",
            "--setenv", "MOZ_HEADLESS=1",
        ]
        if benchmark == "jetstream3":
            command.extend(["--test-url-params", "tag=js&iterationCount=3&worstCaseCount=1"])
        env = os.environ.copy()
        for name in ("MOZ_LOG", "MOZ_LOG_FILE", "IONFLAGS"):
            env.pop(name, None)
        env["MOZCONFIG"] = str(project.parent / "mozconfigs/browser-release.mozconfig")
        started_us = time.time_ns() // 1000
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=firefox,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        emit({"event": "run", "timestamp_us": started_us, "benchmark": benchmark,
              "command": command, "firefox_revision": revision})
        result = subprocess.run(command, cwd=firefox, env=env,
                                stdout=sys.stderr, stderr=sys.stderr)
        files = sorted(log_base.parent.glob(log_base.name + "*.moz_log"))
        counts = {"compile": 0, "install": 0, "discard": 0, "malformed": 0}
        for path in files:
            role = "parent" if path.name == log_base.name + ".moz_log" else "child"
            with path.open(encoding="utf-8", errors="replace") as stream:
                for number, line in enumerate(stream, 1):
                    if "BCACHE\t" not in line:
                        continue
                    try:
                        item = parser.parse_line(line, None)
                    except (KeyError, ValueError, UnicodeError) as error:
                        counts["malformed"] += 1
                        emit({"event": "malformed", "file": path.name,
                              "line": number, "error": str(error), "raw": line.rstrip("\n")})
                        continue
                    item["process_role"] = role
                    counts[item["event"]] += 1
                    emit(item)
        emit({"event": "summary", "timestamp_us": time.time_ns() // 1000,
              "raptor_exit_code": result.returncode, "log_files": len(files), **counts})
        if not files or counts["install"] == 0:
            return 1
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
