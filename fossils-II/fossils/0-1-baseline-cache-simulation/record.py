#!/usr/bin/env python3

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
import baseline_cache_trace as parser
from browser_workloads import MANUAL_SECONDS, PROFILE_PREFS, TESTS, raptor_command


def emit(item):
    print(json.dumps(item, ensure_ascii=True), flush=True)


def run_manual(command, cwd, env, duration=MANUAL_SECONDS):
    print(f"Browse in the new Firefox window for {duration} seconds. "
          "It will close automatically; closing it yourself finishes early.",
          file=sys.stderr, flush=True)
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=env,
                               stdout=sys.stderr, stderr=sys.stderr,
                               start_new_session=True)
    reason = "window_closed"
    forced_kill = False
    try:
        process.wait(timeout=duration)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        reason = "timer" if isinstance(error, subprocess.TimeoutExpired) else "interrupted"
        print("Finishing the browsing capture and collecting traces...",
              file=sys.stderr, flush=True)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            forced_kill = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    expected_stop = reason != "window_closed" and process.returncode == -signal.SIGTERM
    return {
        "exit_code": 0 if process.returncode == 0 or expected_stop else 1,
        "browser_exit_code": process.returncode,
        "stop_reason": reason,
        "forced_kill": forced_kill,
        "recorded_seconds": time.monotonic() - started,
    }


def main():
    benchmark = sys.argv[1]
    if benchmark not in (*TESTS, "manual"):
        raise SystemExit(f"unknown variant: {benchmark}")
    project = Path(__file__).resolve().parents[2]
    firefox = project.parent.parent / "firefox"
    browser = firefox / "build-browser-release/dist/bin/firefox"
    with tempfile.TemporaryDirectory(prefix="baseline-cache-") as directory:
        log_base = Path(directory) / "trace%PID"
        env = os.environ.copy()
        for name in ("MOZ_LOG", "MOZ_LOG_FILE", "IONFLAGS"):
            env.pop(name, None)
        env["MOZCONFIG"] = str(project.parent / "mozconfigs/browser-release.mozconfig")
        run_metadata = {}
        if benchmark == "manual":
            profile = Path(directory) / "profile"
            profile.mkdir()
            (profile / "user.js").write_text(PROFILE_PREFS)
            command = [str(browser), "--no-remote", "--profile", str(profile), "about:blank"]
            env.pop("MOZ_HEADLESS", None)
            env.update(MOZ_LOG="baselineCache:4,sync", MOZ_LOG_FILE=str(log_base))
            run_metadata["capture_duration_seconds"] = MANUAL_SECONDS
        else:
            command = raptor_command(['./mach'], browser, benchmark, {
                'MOZ_LOG': 'baselineCache:4,sync',
                'MOZ_LOG_FILE': str(log_base),
                'MOZ_HEADLESS': '1',
            })
        started_us = time.time_ns() // 1000
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=firefox,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        emit({"event": "run", "timestamp_us": started_us, "benchmark": benchmark,
              "command": command, "firefox_revision": revision, **run_metadata})
        if benchmark == "manual":
            outcome = run_manual(command, firefox, env)
        else:
            result = subprocess.run(command, cwd=firefox, env=env,
                                    stdout=sys.stderr, stderr=sys.stderr)
            outcome = {"exit_code": result.returncode, "raptor_exit_code": result.returncode}
        files = sorted(log_base.parent.glob("trace-*.moz_log"))
        counts = {"compile": 0, "install": 0, "discard": 0, "malformed": 0}
        for path in files:
            role = "parent" if path.name.startswith("trace-main.") else "child"
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
              **outcome, "log_files": len(files), **counts})
        if not files or counts["install"] == 0:
            return 1
        return outcome["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
