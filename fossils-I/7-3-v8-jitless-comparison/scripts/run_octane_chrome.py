#!/usr/bin/env python3
"""Run zlib-excluded Octane 2 in Chromium through the WebDriver protocol."""

import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


WORKLOADS = (
    "Richards",
    "DeltaBlue",
    "Crypto",
    "RayTrace",
    "EarleyBoyer",
    "RegExp",
    "Splay",
    "SplayLatency",
    "NavierStokes",
    "PdfJS",
    "Mandreel",
    "MandreelLatency",
    "Gameboy",
    "CodeLoad",
    "Box2D",
    "Typescript",
)
SCORE_RE = re.compile(r"^Octane Score: ([0-9]+(?:\.[0-9]+)?)$")


def request_json(method, url, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_driver(base_url, process):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ChromeDriver exited with status {process.returncode}")
        try:
            status = request_json("GET", f"{base_url}/status")
            if status.get("value", {}).get("ready"):
                return
        except (URLError, OSError):
            pass
        time.sleep(0.1)
    raise RuntimeError("timed out waiting for ChromeDriver")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", required=True)
    parser.add_argument("--chromedriver", required=True)
    parser.add_argument("--octane-dir", type=Path, required=True)
    parser.add_argument("--jitless", action="store_true")
    args = parser.parse_args()

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="amber-octane-chrome-") as profile:
        environment = dict(__import__("os").environ)
        environment["AMBERMONKEY_CHROMIUM_USER_DATA_DIR"] = profile
        driver = subprocess.Popen(
            [args.chromedriver, f"--port={port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        session_id = None
        try:
            wait_for_driver(base_url, driver)
            chrome_args = [
                "--headless=new",
                "--disable-background-networking",
                "--disable-component-update",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            if args.jitless:
                chrome_args.append("--js-flags=--jitless")
            response = request_json(
                "POST",
                f"{base_url}/session",
                {
                    "capabilities": {
                        "alwaysMatch": {
                            "browserName": "chrome",
                            "goog:chromeOptions": {
                                "binary": args.chrome,
                                "args": chrome_args,
                            },
                        }
                    }
                },
            )
            value = response.get("value", {})
            session_id = value.get("sessionId") or response.get("sessionId")
            if not session_id:
                raise RuntimeError(f"ChromeDriver did not create a session: {response}")

            url = (args.octane_dir / "index.html").resolve().as_uri()
            request_json(
                "POST",
                f"{base_url}/session/{session_id}/url",
                {"url": f"{url}?auto=1&skip_zlib=1"},
            )

            script = """
                const banner = document.getElementById('main-banner').textContent.trim();
                const names = arguments[0];
                const results = {};
                for (const name of names) {
                    const node = document.getElementById('Result-' + name);
                    if (node) results[name] = node.textContent.trim();
                }
                return {banner, results};
            """
            deadline = time.monotonic() + 600
            result = None
            while time.monotonic() < deadline:
                response = request_json(
                    "POST",
                    f"{base_url}/session/{session_id}/execute/sync",
                    {"script": script, "args": [list(WORKLOADS)]},
                )
                result = response.get("value", {})
                if SCORE_RE.match(result.get("banner", "")):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"timed out waiting for Octane: {result}")

            for name in WORKLOADS:
                score = result["results"].get(name)
                if not score or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", score):
                    raise RuntimeError(f"missing Octane result for {name}: {score!r}")
                print(f"{name}: {score}")
            score = SCORE_RE.match(result["banner"]).group(1)
            print("----")
            print(f"Score (version 9): {score}")
        finally:
            if session_id:
                try:
                    request_json("DELETE", f"{base_url}/session/{session_id}")
                except Exception:
                    pass
            driver.terminate()
            try:
                driver.wait(timeout=5)
            except subprocess.TimeoutExpired:
                driver.kill()
                driver.wait()


if __name__ == "__main__":
    main()
