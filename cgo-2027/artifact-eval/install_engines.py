#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import tempfile
from urllib.request import urlopen

MANIFEST = Path(__file__).with_name("releases.json")


def releases():
    return json.loads(MANIFEST.read_text())


def install(name, archives, destination, base_url=None):
    entry = releases()[name]
    target = destination / name
    executable = target / entry["executable"]
    marker = target / ".sha256"
    if marker.is_file() and marker.read_text().strip() == entry["sha256"] and executable.is_file():
        print(f"Already installed: {name}", flush=True)
        return executable
    if target.exists():
        raise ValueError(f"incomplete or different installation: {target}")
    archive = archives / entry["archive"]
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as scratch:
        scratch = Path(scratch)
        if not archive.is_file():
            url = entry.get("url") or (f"{base_url.rstrip('/')}/{entry['archive']}" if base_url else None)
            if not url:
                raise ValueError(f"archive missing: {archive}; supply --base-url for hosted releases")
            archive = scratch / entry["archive"]
            print(f"Downloading {url}", flush=True)
            with urlopen(url, timeout=60) as response, archive.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        print(f"Verifying checksum: {archive}", flush=True)
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"checksum mismatch: {archive}")
        unpacked = scratch / "unpacked"
        unpacked.mkdir()
        print(f"Unpacking {name}", flush=True)
        with tarfile.open(archive) as package:
            package.extractall(unpacked, filter="data")
        binary = unpacked / entry["executable"]
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError(f"executable missing from archive: {entry['executable']}")
        (unpacked / ".sha256").write_text(digest + "\n")
        unpacked.rename(target)
    print(f"Installed {name}", flush=True)
    return executable


def main():
    parser = argparse.ArgumentParser(description="Install verified local or hosted releases.")
    parser.add_argument("releases", nargs="+", choices=list(releases()))
    parser.add_argument("--archives", type=Path, default=Path("/releases"))
    parser.add_argument("--destination", type=Path, default=Path(os.environ.get("AMBERMONKEY_ENGINES", "/opt/engines")))
    parser.add_argument("--base-url", default=os.environ.get("AMBERMONKEY_RELEASE_URL"))
    args = parser.parse_args()
    for name in args.releases:
        install(name, args.archives, args.destination, args.base_url)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, tarfile.TarError) as error:
        raise SystemExit(f"install-engines: {error}")
