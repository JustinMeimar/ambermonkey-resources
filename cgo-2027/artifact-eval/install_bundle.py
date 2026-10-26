#!/usr/bin/env python3
"""Copy the prepared bundle and extracted engines into the image filesystem."""
from pathlib import Path
import shutil
import json

bundle = Path('/bundle')
releases = json.loads((bundle / 'artifact-eval/releases.json').read_text())
for name, release in releases.items():
    target = Path('/engine-cache') / name
    marker = target / '.sha256'
    if (not (target / release['executable']).is_file() or not marker.is_file()
            or marker.read_text().strip() != release['sha256']):
        raise SystemExit(f'Engine cache missing or mismatched: {name}; run setup first')

for source, target in [
    ('resources', '/workspace/ambermonkey-resources-current'),
    ('artifact-eval', '/workspace/artifact-eval-current'),
    ('bin', '/usr/local/bin'),
    ('runtime/nix/store', '/nix/store'),
]:
    shutil.copytree(bundle / source, target, dirs_exist_ok=True, symlinks=True)
engines = Path('/opt/engines')
engines.mkdir(exist_ok=True, parents=True)
for source in Path('/engine-cache').iterdir():
    if source.name == 'uv-cache':
        continue
    shutil.copytree(source, engines / source.name, symlinks=True, dirs_exist_ok=True)
shutil.copy2(bundle / 'bundle-manifest.json', '/workspace/artifact-eval-current/bundle-manifest.json')
entrypoint = Path('/usr/local/bin/ambermonkey-eval')
entrypoint.write_text('''#!/bin/sh
set -eu
if [ "${1:-}" = --suite ]; then
    shift
    exec python3 /workspace/artifact-eval-current/smoke.py "$@"
fi
exec python3 /workspace/artifact-eval-current/run.py "$@"
''')
entrypoint.chmod(0o755)
