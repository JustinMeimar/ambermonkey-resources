#!/usr/bin/env python3
"""Collect existing sources and native tool runtimes; never compile anything."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
bundle = args.destination
bundle.mkdir(parents=True, exist_ok=False)
here = Path(__file__).resolve().parent
resources = here.parents[1]
ignore = shutil.ignore_patterns('records', '.venv', '__pycache__', '*.pyc')
for name in ('fossils-I', 'scripts', 'mozconfigs'):
    shutil.copytree(resources / name, bundle / 'resources' / name,
                    symlinks=True, ignore=ignore)
shutil.copytree(here, bundle / 'artifact-eval', ignore=ignore)
(bundle / 'bin').mkdir()
store_roots = set()
manifest = {'tools': {}}
for name in ('fossil', 'uv', 'perf'):
    executable = shutil.which(name)
    if not executable:
        raise SystemExit(f'missing tool: {name}')
    executable = Path(executable).resolve()
    native = executable.with_name('.perf-wrapped')
    if name == 'perf' and native.is_file():
        executable = native
    shutil.copy2(executable, bundle / 'bin' / name)
    with executable.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    manifest['tools'][name] = {'source': str(executable), 'sha256': digest}
    result = subprocess.run(['ldd', str(executable)], capture_output=True, text=True)
    if result.returncode and 'not a dynamic executable' not in result.stderr + result.stdout:
        raise SystemExit(result.stderr + result.stdout)
    store_roots.update(re.findall(r'/nix/store/[^/\s]+', result.stdout))
    for library in re.findall(r'/nix/store/[^\s]+', result.stdout):
        resolved = Path(library).resolve()
        if str(resolved).startswith('/nix/store/'):
            store_roots.add(str(Path(*resolved.parts[:4])))
for root in sorted(store_roots):
    root = Path(root)
    shutil.copytree(root, bundle / 'runtime/nix/store' / root.name, symlinks=True)
manifest['runtime_roots'] = sorted(store_roots)
manifest['sources'] = {}
for directory in ('resources', 'artifact-eval'):
    for source in sorted((bundle / directory).rglob('*')):
        if source.is_symlink():
            manifest['sources'][str(source.relative_to(bundle))] = {'symlink': str(source.readlink())}
        elif source.is_file():
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            manifest['sources'][str(source.relative_to(bundle))] = {'sha256': digest}

(bundle / 'bundle-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(bundle)
