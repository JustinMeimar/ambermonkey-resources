#!/usr/bin/env python3
"""Capture profiled training and evaluation browser runs for Ion warmup replay."""
import argparse
import hashlib
import importlib.util
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from browser_workloads import raptor_command
import navbench_routes

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox')).resolve()
BROWSER = ROOT / 'build-browser-release/dist/bin/firefox'
ANALYZER = ROOT / 'js/src/jit/ion_recurrence.py'
SCHEMA = 7
# Ion keys include profiler instrumentation, so both phases are profiled alike.
PROFILER = {
    'MOZ_PROFILER_STARTUP': '1',
    'MOZ_PROFILER_STARTUP_FEATURES': 'js,cpu',
    'MOZ_PROFILER_STARTUP_FILTERS': 'GeckoMain,DOM Worker',
    'MOZ_PROFILER_STARTUP_INTERVAL': '1',
    'MOZ_PROFILER_STARTUP_ENTRIES': '1GiB',
}
# Hints lower Ion thresholds within a runtime; the analysis derives their effect.
PREFS = {'javascript.options.jithints': 'false'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(variant, plan, directory):
    environment = {
        'MOZ_LOG': 'ionRecurrence:3,sync' + (',append' if plan else ''),
        'MOZ_LOG_FILE': str(directory / 'trace%PID'),
        **PROFILER,
        'MOZ_PROFILER_SHUTDOWN': str(directory / 'profile.json'),
        'MOZ_HEADLESS': '1',
    }
    if plan:
        return navbench_routes.browsertime_command(ROOT, BROWSER, plan, directory,
                                                   environment)
    command = raptor_command(['./mach'], BROWSER, variant, environment)
    for name, value in PREFS.items():
        command.extend(['--setpref', f'{name}={value}'])
    return command


def check_coverage(replay, records, profile):
    if not profile.exists():
        raise ValueError(f'no shutdown profile at {profile}')
    valid = [r for r in records if r['key_valid']]
    result = replay.warmup(valid, replay.read_profile(profile), {})
    return {'profiled_threads': len(result['threads']),
            'attributed_functions': len(result['functions']),
            'excluded': result['excluded'],
            'max_process_start_skew_us': result['max_process_start_skew_us']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('speedometer3', 'jetstream3',
                                            *navbench_routes.routes()))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    directory = ROOT / 'artifacts/ion-warmup' / f'{time.time_ns()}-{args.variant}'
    plan = (navbench_routes.workload(args.variant)
            if args.variant in navbench_routes.routes() else None)
    commands = {phase: command(args.variant, plan, directory / phase)
                for phase in ('training', 'evaluation')}
    if args.dry_run:
        print(json.dumps({'workload': plan, 'commands': commands}, indent=2))
        return
    with (BROWSER.parent / 'libxul.so').open('rb') as library:
        with mmap.mmap(library.fileno(), 0, access=mmap.ACCESS_READ) as contents:
            if contents.find(b'IONREC {"schema":%d,' % SCHEMA) < 0:
                sys.exit(f'Rebuild the release browser with schema {SCHEMA} '
                         'Ion recurrence logging.')
    spec = importlib.util.spec_from_file_location('ion_recurrence', ANALYZER)
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    directory.mkdir(parents=True)
    metadata = {
        'variant': args.variant, 'directory': str(directory), 'schema': SCHEMA,
        'workload': plan, 'commands': commands, 'browser': str(BROWSER),
        'profiler': PROFILER, 'prefs': PREFS,
        'libxul_sha256': digest(BROWSER.parent / 'libxul.so'),
        'analyzer_sha256': digest(ANALYZER),
        'firefox_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'started_ns': time.time_ns(),
    }
    (directory / 'firefox.diff').write_bytes(subprocess.check_output(
        ['git', 'diff', 'HEAD', '--', 'js/src'], cwd=ROOT))
    (directory / 'ion_recurrence.py').write_bytes(ANALYZER.read_bytes())
    (directory / 'runner.py').write_bytes(Path(__file__).read_bytes())
    (directory / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    env = dict(os.environ)
    for name in ('MOZ_LOG', 'MOZ_LOG_FILE', 'IONFLAGS', 'JS_SPECIALIZATION_HINTS',
                 *PROFILER, 'MOZ_PROFILER_SHUTDOWN'):
        env.pop(name, None)
    env['MOZCONFIG'] = str(ROOT.parent / 'ambermonkey/mozconfigs/browser-release.mozconfig')
    if plan:
        env['MOZ_DISABLE_NONLOCAL_CONNECTIONS'] = '0'
    phases = {}
    for phase, invocation in commands.items():
        capture = directory / phase
        capture.mkdir()
        if plan:
            navbench_routes.prepare_profile(ROOT, capture)
            with (capture / 'profile/user.js').open('a') as prefs:
                for name, value in PREFS.items():
                    prefs.write(f'user_pref("{name}", {value});\n')
        print(f'{args.variant}: {phase}; logs in {capture}', file=sys.stderr, flush=True)
        with (capture / 'harness.log').open('w') as log:
            status = subprocess.run(invocation, cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT).returncode
        (capture / 'exit-code.json').write_text(json.dumps(status) + '\n')
        if status:
            sys.exit(f'{phase} failed ({status}); see {capture / "harness.log"}')
        if plan:
            try:
                navbench_routes.validate_visits(plan, capture)
            except ValueError as error:
                sys.exit(f'{phase}: {error}')
        records, unfinished = replay.read_traces(sorted(capture.glob('trace*.moz_log')))
        guest = [r for r in records if not r['self_hosted'] and not r['system']]
        if not any(r['key_valid'] and r['outcome'] == 'installed' for r in guest):
            sys.exit(f'{phase}: no installed guest compilations with valid keys')
        try:
            coverage = check_coverage(replay, guest, capture / 'profile.json')
        except (OSError, KeyError, ValueError) as error:
            sys.exit(f'{phase}: {error}')
        phases[phase] = (guest, unfinished, len(records) - len(guest), coverage)
    if digest(BROWSER.parent / 'libxul.so') != metadata['libxul_sha256']:
        sys.exit('Browser changed during capture; discard this pair.')
    training, training_unfinished, training_excluded, training_coverage = phases['training']
    evaluation, unfinished, excluded, coverage = phases['evaluation']
    reports = {scope: replay.analyze(evaluation, scope=scope)
               for scope in ('runtime', 'process', 'shared')}
    reports['prepopulated'] = replay.analyze(evaluation, training=training, scope='shared')
    result = {
        **metadata, 'reports': reports,
        'profile_coverage': coverage,
        'training_profile_coverage': training_coverage,
        'unfinished_requests': unfinished,
        'unfinished_training_requests': training_unfinished,
        'excluded_system_or_self_hosted': excluded,
        'training_excluded_system_or_self_hosted': training_excluded,
        'training_finished_guest_requests': len(training),
        'completed_ns': time.time_ns(),
    }
    (directory / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
