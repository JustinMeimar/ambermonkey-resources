#!/usr/bin/env python3
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE.parent / 'common'))
import baseline_cache_trace as baseline
from browser_workloads import MANUAL_SECONDS, PROFILE_PREFS, TESTS, raptor_command
from progress import progress, run_logged

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox')).resolve()
WRAPPER = PACKAGE / 'run-browser'
BROWSER = ROOT / 'build-browser-release/dist/bin/firefox'
ANALYZER = PACKAGE / 'specialization_cache.py'


def build_identity():
    digest = hashlib.sha256()
    for path in [BROWSER, BROWSER.parent / 'libxul.so', ROOT / 'build-browser-release/mozinfo.json']:
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    return 'browser-x64-opt-' + digest.hexdigest()[:20]


def preflight():
    try:
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen(1)
    except OSError as error:
        raise RuntimeError(f'Browser recording requires loopback sockets: {error}. '
                           'Run this command from a terminal/session with loopback networking.') from error
    if 2 not in os.sched_getaffinity(0):
        raise RuntimeError('CPU 2 is unavailable; cannot match the original recording affinity.')


def extract(directory, label, build_id):
    logs = sorted(directory.glob('trace*.moz_log'))
    if not logs:
        raise RuntimeError('No browser trace files were produced.')
    with (directory / 'specialization.jsonl').open('w') as stream:
        subprocess.run([sys.executable, str(ANALYZER), 'extract', '--run', label,
                        *map(str, logs)], stdout=stream, check=True)
    counts = Counter()
    pids = set()
    hinted_pids = set()
    definitions = set()
    references = set()
    seen = set()
    with (directory / 'specialization.jsonl').open() as stream:
        for line in stream:
            event = json.loads(line)
            if event['build_id'] != build_id:
                raise RuntimeError('Mismatched build ID in browser trace.')
            process = (event['pid'], event['process_start_us'])
            event_id = (*process, event['sequence'])
            if event_id in seen:
                raise RuntimeError(f'Duplicate trace event: {event_id}')
            seen.add(event_id)
            pids.add(event['pid'])
            counts[event['event']] += 1
            if 'ic_script' in event:
                references.add((*process, event['ic_script']))
            if event['event'] == 'script':
                definitions.add((*process, event['ic_script']))
                if event['hint_threshold']:
                    hinted_pids.add(event['pid'])
    if references - definitions:
        raise RuntimeError(f'Trace has {len(references - definitions)} undefined script lifetimes.')
    if not counts['ion_request'] or not counts['selected']:
        raise RuntimeError('Trace has no analyzable Ion specialization activity.')
    baseline_counts = Counter()
    with (directory / 'baseline.jsonl').open('w') as stream:
        for path in logs:
            with path.open() as source:
                for line in source:
                    if 'BCACHE\t' in line:
                        event = baseline.parse_line(line, None)
                        baseline_counts[event['event']] += 1
                        stream.write(json.dumps(event) + '\n')
    return {'log_files': len(logs), 'pids': sorted(pids), 'hinted_pids': sorted(hinted_pids),
            'specialization_events': dict(counts), 'baseline_events': dict(baseline_counts)}


def main():
    parser = argparse.ArgumentParser(description='Repeat the Baseline-cache browser workloads with specialization tracing.')
    parser.add_argument('workload', choices=[*TESTS, 'manual'])
    parser.add_argument('--run', required=True, help='Unique independent recording label, e.g. train-a')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/specialization-browser/runs')
    parser.add_argument('--hints', type=Path)
    parser.add_argument('--no-trace', action='store_true', help='Retain Raptor scores without instrumentation')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.run or Path(args.run).name != args.run or args.run in ('.', '..'):
        parser.error('--run must be one directory name')
    directory = args.output.resolve() / args.workload / args.run
    log_options = 'baselineCache:4,specializationCache:4,sync,append'
    inherited = os.environ.copy()
    for key in ['MOZ_LOG', 'MOZ_LOG_FILE', 'IONFLAGS', 'JS_SPECIALIZATION_HINTS', 'MOZ_HEADLESS']:
        inherited.pop(key, None)
    overrides = {}
    if not args.no_trace:
        overrides.update(MOZ_LOG=log_options, MOZ_LOG_FILE=str(directory / 'trace%PID'))
    if args.hints:
        overrides['JS_SPECIALIZATION_HINTS'] = str(args.hints.resolve())
    if args.workload == 'manual':
        command = ['taskset', '-c', '2', str(WRAPPER), 'exec', str(BROWSER), '--no-remote',
                   '--profile', str(directory / 'profile'), 'about:blank']
    else:
        command = raptor_command(['taskset', '-c', '2', str(WRAPPER)], BROWSER, args.workload)
        overrides['MOZ_HEADLESS'] = '1'
    plan = {'workload': args.workload, 'run': args.run, 'directory': str(directory),
            'command': command, 'environment': overrides, 'cpu': 2, 'manual_seconds': MANUAL_SECONDS,
            'notes': ['Fresh execution; original Baseline logs cannot supply IC/Ion history.',
                      'PID-qualified, append, synchronous logs; strict extraction.',
                      'Training and evaluation must use separate browser recordings.']}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    preflight()
    info = json.loads((ROOT / 'build-browser-release/mozinfo.json').read_text())
    if info.get('debug') or not info.get('opt'):
        raise RuntimeError('Expected optimized, non-debug browser.')
    if args.hints and not args.hints.is_file():
        raise RuntimeError(f'Missing hint file: {args.hints}')
    progress('Hashing browser build for provenance')
    build_id = build_identity()
    overrides['JS_SPECIALIZATION_BUILD_ID'] = build_id
    if args.workload != 'manual':
        for key, value in overrides.items():
            command += ['--setenv', f'{key}={value}']
    directory.mkdir(parents=True, exist_ok=False)
    inherited.update(overrides)
    inherited['MOZ_UPLOAD_DIR'] = str(directory / 'raptor-results')
    Path(inherited['MOZ_UPLOAD_DIR']).mkdir()
    inherited['XDG_CACHE_HOME'] = str(directory / 'cache')
    if args.workload == 'manual':
        profile = directory / 'profile'
        profile.mkdir()
        (profile / 'user.js').write_text(PROFILE_PREFS)
    plan.update(build_id=build_id, started_us=time.time_ns() // 1000,
                firefox_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    host = {'affinity': sorted(os.sched_getaffinity(0)), 'uname': list(os.uname())}
    for name, path in {
        'governor': '/sys/devices/system/cpu/cpu2/cpufreq/scaling_governor',
        'boost': '/sys/devices/system/cpu/cpufreq/boost',
        'intel_no_turbo': '/sys/devices/system/cpu/intel_pstate/no_turbo',
    }.items():
        try:
            host[name] = Path(path).read_text().strip()
        except OSError:
            host[name] = None
    plan['host'] = host
    with (directory / 'tracked-diff.patch').open('w') as diff:
        subprocess.run(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT,
                       stdout=diff, check=True)
    for name in ('SpecializationTrace.cpp', 'SpecializationTrace.h'):
        (directory / name).write_bytes((ROOT / 'js/src/jit' / name).read_bytes())
    (directory / 'mozinfo.json').write_text(json.dumps(info, indent=2) + '\n')
    config = Path(info['mozconfig'])
    (directory / 'mozconfig').write_bytes(config.read_bytes())
    (directory / 'run.json').write_text(json.dumps(plan, indent=2) + '\n')
    progress(f'Recording {args.workload}/{args.run} to {directory}')
    status = run_logged(command, ROOT, inherited, directory,
                        duration=MANUAL_SECONDS if args.workload == 'manual' else None)
    summary = {'exit_code': status, 'ended_us': time.time_ns() // 1000, 'build_id': build_id}
    if status:
        (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        raise RuntimeError(f'Browser harness exited {status}; logs retained in {directory}')
    if not args.no_trace:
        progress('Extracting and validating specialization and Baseline traces')
        summary.update(extract(directory, f'{args.workload}-{args.run}', build_id))
    if args.hints:
        with (directory / 'harness.log').open() as stream:
            if any('Specialization hints: cannot open' in line or 'Specialization hints: invalid' in line for line in stream):
                raise RuntimeError('Browser rejected/could not open hints; this is not a valid treatment.')
        if not args.no_trace and not summary['hinted_pids']:
            raise RuntimeError('No hint activation observed; treatment is unverified.')
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
