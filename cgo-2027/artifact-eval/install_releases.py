#!/usr/bin/env python3
"""Verify and unpack every archive in releases.json (runs once, at image build)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

archives, engines = Path(sys.argv[1]), Path(sys.argv[2])
for name, release in json.loads(Path(__file__).with_name('releases.json').read_text()).items():
    archive = archives / release['archive']
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != release['sha256']:
            raise SystemExit(f'checksum mismatch: {archive}')
    target = engines / name
    target.mkdir(parents=True)
    print(f'Unpacking {name}', flush=True)
    if archive.suffix == '.zip':
        with zipfile.ZipFile(archive) as package:
            package.extractall(target)
        (target / release['executable']).chmod(0o755)
    elif archive.suffix == '.zst':
        with subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE) as decoded:
            with tarfile.open(fileobj=decoded.stdout, mode='r|') as package:
                package.extractall(target, filter='data', members=(
                    m for m in package if m.name not in release.get('exclude', [])))
    else:
        with tarfile.open(archive) as package:
            package.extractall(target, filter='data')
    # Browser archives hold firefox/; the size measurements expect a build-style dist/bin.
    if release['executable'].startswith('dist/bin/'):
        (target / 'dist').mkdir()
        (target / 'firefox').rename(target / 'dist/bin')
    if not os.access(target / release['executable'], os.X_OK):
        raise SystemExit(f'{name}: missing executable {release["executable"]}')
