#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from analyze import read_events, summarize
from navbench_routes import browsertime_command, prepare_profile, validate_visits
from workloads import command_override, variants, workload

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox'))
OBJDIR = ROOT / 'build-browser-release'
BROWSER = OBJDIR / 'dist/bin/firefox'


def browser_command(plan, directory):
    environment = {'MOZ_LOG': 'ionRecurrence:3,sync,append',
                   'MOZ_LOG_FILE': f'{directory}/trace%PID'}
    if plan['variant'] != 'navbench':
        return browsertime_command(ROOT, BROWSER, plan, directory, environment)
    return ['./mach', 'raptor', '-t', 'nav-bench', '--app', 'firefox',
            '--binary', str(BROWSER), '--browser-cycles', '1',
            *(arg for key, value in environment.items()
              for arg in ('--setenv', f'{key}={value}')),
            *command_override(plan)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=variants())
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the workload and command without launching Firefox')
    args = parser.parse_args()
    plan = workload(args.variant, ROOT)
    plan['mode'] = 'recorded' if args.variant == 'navbench' else 'live'
    directory = ROOT / 'artifacts/ion-recurrence' / f'{time.time_ns()}-{args.variant}'
    command = browser_command(plan, directory)
    if args.dry_run:
        print(json.dumps({'workload': plan, 'command': command}, indent=2))
        return
    if b'IONREC {"schema":2,' not in (OBJDIR / 'dist/bin/libxul.so').read_bytes():
        sys.exit('libxul.so needs schema 2 Ion recurrence logging; rebuild first.')
    directory.mkdir(parents=True)
    if plan['mode'] == 'live':
        prepare_profile(ROOT, directory)
    (directory / 'workload.json').write_text(json.dumps(plan, indent=2) + '\n')
    mozconfig = json.loads((OBJDIR / 'mozinfo.json').read_text())['mozconfig']
    env = dict(os.environ, MOZCONFIG=mozconfig, MOZ_UPLOAD_DIR=str(directory / 'raptor'))
    if plan['mode'] == 'live':
        env['MOZ_DISABLE_NONLOCAL_CONNECTIONS'] = '0'
    print(f"Running {args.variant} ({plan['mode']}); log: {directory / 'harness.log'}",
          file=sys.stderr, flush=True)
    with (directory / 'harness.log').open('w') as log:
        status = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT).returncode
    if status:
        sys.exit(f'NavBench failed with exit code {status}; see {directory / "harness.log"}')
    # The interactive driver catches command failures. A successful harness
    # exit alone does not mean the requested route completed.
    if 'Exception found while running' in (directory / 'harness.log').read_text(errors='replace'):
        sys.exit(f'NavBench navigation command failed; see {directory / "harness.log"}')
    if plan['mode'] == 'live':
        validate_visits(plan, directory)
    events = read_events(directory)
    compilations = sum(event['event'] == 'compile' for event in events)
    if not compilations:
        sys.exit(f'No Ion recurrence compilation records; see {directory}')
    if any(event.get('schema') != 2 for event in events):
        sys.exit('Unexpected Ion recurrence schema; rebuild the release browser.')
    summarize(events)
    for event in events:
        print('IONREC ' + json.dumps(event, separators=(',', ':')))
    print(json.dumps({'directory': str(directory), 'exit_code': status,
                      'browser': str(BROWSER), 'events': len(events),
                      'compilations': compilations, 'workload': plan}))


if __name__ == '__main__':
    main()
