#!/usr/bin/env python3
"""Bounded smoke runs using packaged engines and the current Fossil CLI."""
import argparse
import json
import hashlib
import time
import os
from pathlib import Path
import shutil
import signal
import shlex
import subprocess
import tomllib

import configure as setup


def command(argv, timeout):
    argv = list(map(str, argv))
    logs = setup.RESULTS / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    stem = str(time.time_ns())
    log = logs / f'{stem}.log'
    report_path = logs / f'{stem}.json'
    report = {'argv': argv, 'timeout_seconds': timeout, 'status': 'running',
              'log': str(log), 'started_unix': time.time()}
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('==> ' + ' '.join(argv), flush=True)
    print(f'    Log: {log}', flush=True)
    started = time.monotonic()
    with log.open('w') as output:
        process = subprocess.Popen(argv, start_new_session=True,
                                   stdout=output, stderr=subprocess.STDOUT)
        try:
            status = process.wait(timeout=timeout)
            report['status'] = 'passed' if status == 0 else 'failed'
        except subprocess.TimeoutExpired:
            report['status'] = 'timed_out'
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            status = process.wait()
    report.update(exit_code=status, duration_seconds=time.monotonic() - started)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'    {report["status"]} ({report["duration_seconds"]:.1f}s)', flush=True)
    if report['status'] != 'passed':
        print('\n'.join(log.read_text(errors='replace').splitlines()[-20:]), flush=True)
        raise ValueError(f'{report["status"]}: see {log}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('names', nargs='*')
    parser.add_argument('-n', '--iterations', type=int, default=1)
    parser.add_argument('--variant', default='default')
    parser.add_argument('--timeout', type=int, default=180, help='seconds per Fossil command')
    parser.add_argument('--setup-only', action='store_true')
    parser.add_argument('--prepare-figures', action='store_true', help='install locked figure wheels without compiling')
    parser.add_argument('--artifact', action='append', default=[], help='emit a named artifact for the selected variant')
    parser.add_argument('--emit-only', action='store_true', help='emit from existing records without running a benchmark')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.iterations < 1 or args.timeout < 1:
        parser.error('iterations and timeout must be positive')
    if args.emit_only and not args.artifact:
        parser.error('--emit-only requires --artifact')
    source = Path(os.environ.get('AMBERMONKEY_INPUT', '/input'))
    if not (setup.RESOURCES / 'fossils-I').exists():
        for name in ('fossils-I', 'scripts', 'mozconfigs'):
            shutil.copytree(source / name, setup.RESOURCES / name,
                            ignore=shutil.ignore_patterns('records', '.venv', '__pycache__'),
                            symlinks=True)
    for name, release in setup.releases().items():
        if release.get('optional') and not set(release.get('experiments', [])) & set(args.names):
            continue
        setup.install(name, Path('/releases'), setup.ENGINES)
    setup.configure_fossil()
    project = setup.RESOURCES / 'fossils-I'
    definitions = {p.parent.name: tomllib.loads(p.read_text())
                   for p in (project / 'fossils').glob('*/fossil.toml')}
    for name in definitions:
        setup.configure_records(name)
    os.environ['AMBERMONKEY_CORPUS'] = str(setup.RESULTS / 'corpus')
    os.environ['AMBERMONKEY_SELFHOSTED'] = str(setup.RESULTS / 'self-hosted')
    os.environ['AMBERMONKEY_BIN_RELEASE'] = str(setup.browser_layout(setup.executable('default-browser-release')))
    os.environ['AMBERMONKEY_JSSHELL_AOT'] = str(setup.executable('default-shell-release'))
    mozconfig = setup.RESOURCES / 'artifact-raptor.mozconfig'
    mozconfig.write_text('mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-x86_64-pc-linux-gnu\n')
    os.environ['AMBERMONKEY_MOZCONFIG_AOT'] = str(mozconfig)
    os.environ['AMBERMONKEY_MOZCONFIG_RELEASE'] = str(mozconfig)
    os.environ['AMBERMONKEY_TALOS_LAUNCHER'] = str(Path(__file__).with_name('run_talos.py').resolve())
    if '7-3-v8-jitless-comparison' in args.names:
        v8 = setup.RESOURCES / 'v8-project'
        v8.mkdir(exist_ok=True)
        for name, argv in (
            ('run-chromium-nixos.sh', [setup.executable('chromium-no-pgo'), '--no-sandbox']),
            ('run-chromedriver-nixos.sh', [setup.executable('chromedriver-155')]),
        ):
            wrapper = v8 / name
            wrapper.write_text('#!/bin/sh\nexec ' + shlex.join(list(map(str, argv))) + ' "$@"\n')
            wrapper.chmod(0o755)
        os.environ['AMBERMONKEY_V8'] = str(v8)
    if args.artifact or args.prepare_figures:
        figure_environment = setup.ENGINES / 'figure-venv'
        lock_digest = hashlib.sha256((project / 'uv.lock').read_bytes()).hexdigest()
        marker = figure_environment / '.artifact-lock'
        if not marker.is_file() or marker.read_text().strip() != lock_digest:
            os.environ['UV_PROJECT_ENVIRONMENT'] = str(figure_environment)
            os.environ['UV_CACHE_DIR'] = str(setup.ENGINES / 'uv-cache')
            command(['uv', 'sync', '--locked', '--no-build', '--no-python-downloads',
                     '--python', '/usr/bin/python3', '--project', project], args.timeout)
            marker.write_text(lock_digest + '\n')
        environment_link = project / '.venv'
        if not environment_link.exists():
            environment_link.symlink_to(figure_environment, target_is_directory=True)
    if '7-5-indirection-overhead' in args.names:
        for key, suffix in [('RIT', 'rit'), ('NATIVE_LINKER', 'native-linker'),
                            ('NATIVE_LINKER_VALUE_MIRROR', 'native-linker-value-mirror')]:
            os.environ[f'AMBERMONKEY_JSSHELL_{key}'] = str(setup.executable(f'indirection-{suffix}-candidate'))
    if args.setup_only:
        return
    prefix = [setup.FOSSIL, '--home', setup.FOSSIL_HOME, '--project', 'ambermonkey']
    names = args.names or ['0-0-static-tables', '7-6-binary-size', '7-2-ambermonkey-perf-octane']
    for name in names:
        if name not in definitions or (name not in setup.SUPPORTED and name != '0-0-static-tables'):
            raise ValueError(f'{name}: ' + setup.UNAVAILABLE.get(name, 'prerequisites not configured'))
        definition = definitions[name]
        for artifact in args.artifact:
            if artifact not in definition.get('artifacts', {}):
                raise ValueError(f'unknown artifact {artifact} for {name}')
            required = definition['artifacts'][artifact].get('required-variants', [])
            if set(required) - {args.variant}:
                raise ValueError(f'{name}/{artifact} requires variants {required}; this runner selects only {args.variant}')
        if setup.SUPPORTED.get(name) and name != '7-2-ambermonkey-perf-octane':
            os.environ['AMBERMONKEY_BIN_AOT'] = str(setup.browser_layout(setup.executable(setup.SUPPORTED[name])))
        if definition.get('variants'):
            allowed = setup.VARIANTS.get(name, definition['variants'])
            if name == '6-1-corpus-construction':
                allowed = [v for v in allowed if v != 'self-hosted']
            if args.variant not in allowed:
                raise ValueError(f'unavailable variant {args.variant} for {name}; allowed: {list(allowed)}')
            if not args.emit_only:
                command([*prefix, 'bury', name, '-n', str(args.iterations), '--variant', args.variant,
                         *(['--dry-run'] if args.dry_run else [])], args.timeout)
                if not args.dry_run and definition.get('analyses'):
                    command([*prefix, 'analyze', f'{name}:{args.variant}', '--last', '1'], args.timeout)
            for artifact in args.artifact:
                if not args.dry_run:
                    command([*prefix, 'emit', name, '--artifact', artifact,
                             '--variant', args.variant, '--last', '1'], args.timeout)
        else:
            artifacts = args.artifact or (('browser',) if name == '7-6-binary-size' else definition.get('artifacts', {}))
            for artifact in artifacts:
                if not args.dry_run:
                    command([*prefix, 'emit', name, '--artifact', artifact], args.timeout)
    print(f'Results: {setup.RESULTS}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'artifact-eval: {error}')
