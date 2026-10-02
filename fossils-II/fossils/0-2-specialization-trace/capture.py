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
import specialization_cache as sc
from browser_workloads import MANUAL_SECONDS, PROFILE_PREFS, TESTS, raptor_command
from progress import progress, run_logged

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox')).resolve()
WRAPPER = PACKAGE / 'run-browser'
BROWSER = ROOT / 'build-browser-release/dist/bin/firefox'


def build_identity(require_trace=True):
    digest = hashlib.sha256()
    framed_trace = False
    for path in [BROWSER, BROWSER.parent / 'libxul.so', ROOT / 'build-browser-release/mozinfo.json']:
        with path.open('rb') as stream:
            previous = b''
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
                if path.name == 'libxul.so' and b'IONFEEDBACK\t' in previous + chunk:
                    framed_trace = True
                previous = chunk[-16:]
    if require_trace and not framed_trace:
        raise RuntimeError('Browser lacks compilation feedback instrumentation; rebuild before recording.')
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
    counts = Counter()
    temporary = directory / 'specialization.jsonl.tmp'
    with temporary.open('w') as stream:
        for event in sc.extract(logs, label):
            if event['build_id'] != build_id:
                raise RuntimeError('Mismatched build ID in browser trace.')
            counts[event['event']] += 1
            stream.write(json.dumps(event, separators=(',', ':')) + '\n')
    if not counts['ion_request'] or not counts['profile'] or not counts['ion_link']:
        raise RuntimeError('Trace has no analyzable Ion activity.')
    temporary.replace(directory / 'specialization.jsonl')
    sc.read_recording(directory)
    return {'log_files': len(logs),
            'trace_bytes': sum(p.stat().st_size for p in logs),
            'specialization_events': dict(counts)}


def main():
    parser = argparse.ArgumentParser(description='Record Ion compilation feedback at default thresholds.')
    parser.add_argument('workload', choices=[*TESTS, 'manual'])
    parser.add_argument('--run', required=True, help='Unique independent recording label, e.g. train-a')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/specialization-browser/runs')
    parser.add_argument('--no-trace', action='store_true', help='Retain Raptor scores without instrumentation')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.run or Path(args.run).name != args.run or args.run in ('.', '..'):
        parser.error('--run must be one directory name')
    directory = args.output.resolve() / args.workload / args.run
    log_options = 'specializationCache:4,sync,append'
    inherited = os.environ.copy()
    for key in ['MOZ_LOG', 'MOZ_LOG_FILE', 'IONFLAGS', 'JS_SPECIALIZATION_HINTS', 'MOZ_HEADLESS']:
        inherited.pop(key, None)
    overrides = {}
    if not args.no_trace:
        overrides.update(MOZ_LOG=log_options, MOZ_LOG_FILE=str(directory / 'trace%PID'))
    if args.workload == 'manual':
        command = ['taskset', '-c', '2', str(WRAPPER), 'exec', str(BROWSER), '--no-remote',
                   '--profile', str(directory / 'profile'), 'about:blank']
    else:
        command = raptor_command(['taskset', '-c', '2', str(WRAPPER)], BROWSER, args.workload)
        overrides['MOZ_HEADLESS'] = '1'
    plan = {'workload': args.workload, 'run': args.run, 'directory': str(directory),
            'command': command, 'environment': overrides, 'cpu': 2, 'manual_seconds': MANUAL_SECONDS,
            'notes': ['Fresh execution; original Baseline logs cannot supply IC/Ion history.',
                      'Framed feedback events; synchronous logs; strict extraction.',
                      'Training and evaluation must use separate browser recordings.']}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return
    preflight()
    info = json.loads((ROOT / 'build-browser-release/mozinfo.json').read_text())
    if info.get('debug') or not info.get('opt'):
        raise RuntimeError('Expected optimized, non-debug browser.')
    progress('Hashing browser build for provenance')
    build_id = build_identity(require_trace=not args.no_trace)
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
        progress('Extracting framed Ion compilation traces')
        try:
            summary.update(extract(directory, f'{args.workload}-{args.run}', build_id))
        except (OSError, ValueError, RuntimeError) as error:
            summary.update(exit_code=1, extraction_error=str(error))
            (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            raise
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
