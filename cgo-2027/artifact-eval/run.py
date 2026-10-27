#!/usr/bin/env python3
"""Run the AmberMonkey evaluation (paper section 7) inside the artifact image.

Each experiment buries every variant with Fossil, checks that all observations
succeeded, analyzes them, then emits the paper's tables and figures. Results
go to /results/<run>/; rerun with --resume <run> to continue after a failure.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / 'evaluation.json').read_text())
PROJECT = Path('/workspace/fossils-I')
FOSSIL = ['fossil', '--project', 'ambermonkey-cgo']


def check_records(run, name, variant, iterations):
    """Fail unless the newest record of a variant has every observation exiting 0."""
    records = []
    for manifest in (run / 'records' / name).glob('*/manifest.json'):
        data = json.loads(manifest.read_text())
        if data.get('variant') == variant:
            records.append((data['timestamp'], manifest.parent))
    if not records:
        raise RuntimeError('no record produced')
    observations = json.loads((max(records)[1] / 'results.json').read_text())['observations']
    passed = sum(o.get('exit_code') == 0 for o in observations)
    if len(observations) != iterations or passed != iterations:
        raise RuntimeError(f'{passed}/{iterations} observations succeeded')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--list', action='store_true', help='print the plan and exit')
    parser.add_argument('--only', action='append', metavar='EXPERIMENT',
                        choices=[e['experiment'] for e in PLAN], help='run selected experiments (repeatable)')
    parser.add_argument('-n', '--iterations', type=int, help="override every experiment's repetition count")
    parser.add_argument('--resume', metavar='RUN', help='continue a previous run, skipping passed steps')
    parser.add_argument('--timeout', type=int, default=1200, help='seconds per observation (default 1200)')
    args = parser.parse_args()
    plan = [e for e in PLAN if not args.only or e['experiment'] in args.only]
    # The prebuilt AOT images contain AVX2 and BMI2 instructions recorded on the build host.
    flags = set(Path('/proc/cpuinfo').read_text().split())
    missing = [flag for flag in ('avx2', 'bmi2') if flag not in flags]
    if missing and not args.list:
        sys.exit(f"error: this CPU lacks {', '.join(missing)}; the AmberMonkey AOT images need x86-64 with "
                 "AVX2 and BMI2 (Intel Haswell 2013+, AMD Zen). In a VM, set the CPU type to 'host'.")
    if args.list:
        for entry in plan:
            print(f"{entry['experiment']}  n={args.iterations or entry['iterations']}")
            print(f"  variants: {', '.join(entry['variants']) or '(static)'}")
            print(f"  outputs:  {', '.join(entry['artifacts']) or '(analysis only)'}")
            if 'note' in entry:
                print(f"  note:     {entry['note']}")
        return 0

    run = Path('/results') / (args.resume or time.strftime('run-%Y%m%d-%H%M%S'))
    (run / 'logs').mkdir(parents=True, exist_ok=bool(args.resume))
    status_path = run / 'status.json'
    status = json.loads(status_path.read_text()) if args.resume else {}

    # Point the Fossil project's records and artifact directories into this run.
    config = PROJECT / 'project.toml'
    config.write_text(''.join(f'artifact_dir = "{run}/artifacts"\n' if line.startswith('artifact_dir') else line
                              for line in config.read_text().splitlines(keepends=True)))
    for entry in PLAN:
        records = PROJECT / 'fossils' / entry['experiment'] / 'records'
        (run / 'records' / entry['experiment']).mkdir(parents=True, exist_ok=True)
        if records.is_symlink() or records.exists():
            records.unlink()
        records.symlink_to(run / 'records' / entry['experiment'])

    def step(key, argv, env, timeout, check=None):
        if status.get(key, {}).get('status') == 'passed':
            print(f'[skip] {key}', flush=True)
            return True
        log = run / 'logs' / (key.replace('/', '__') + '.log')
        print(f'[run ] {key}  (log: {log})', flush=True)
        started = time.monotonic()
        with log.open('w') as output:
            try:
                code = subprocess.run(argv, env=env, stdout=output, stderr=subprocess.STDOUT,
                                      timeout=timeout).returncode
                result = 'passed' if code == 0 else f'failed (exit {code})'
                if code == 0 and check:
                    check()
            except subprocess.TimeoutExpired:
                result = 'timed out'
            except RuntimeError as error:
                result = f'failed ({error})'
        status[key] = {'status': 'passed' if result == 'passed' else 'failed', 'detail': result,
                       'seconds': round(time.monotonic() - started, 1), 'log': str(log)}
        status_path.write_text(json.dumps(status, indent=2) + '\n')
        print(f'[{"ok" if result == "passed" else "FAIL"}  ] {key}: {result}', flush=True)
        if result != 'passed':
            print(''.join(log.read_text(errors='replace').splitlines(keepends=True)[-15:]), flush=True)
        return result == 'passed'

    print(f'Results: {run}', flush=True)
    for entry in plan:
        name = entry['experiment']
        n = args.iterations or entry['iterations']
        complete = True
        for variant in entry['variants']:
            env = {**os.environ, **entry.get('env', {}), **entry.get('variant_env', {}).get(variant, {})}
            complete &= (step(f'{name}/{variant}/bury', [*FOSSIL, 'bury', name, '-n', str(n), '--variant', variant],
                              env, args.timeout * n, lambda: check_records(run, name, variant, n))
                         and step(f'{name}/{variant}/analyze', [*FOSSIL, 'analyze', f'{name}:{variant}', '--last', '1'],
                                  env, args.timeout))
        for artifact in entry['artifacts']:
            if complete:
                step(f'{name}/emit/{artifact}', [*FOSSIL, 'emit', name, '--artifact', artifact],
                     {**os.environ, **entry.get('env', {})}, args.timeout)
            else:
                status[f'{name}/emit/{artifact}'] = {'status': 'failed', 'detail': 'skipped: a variant failed'}
                status_path.write_text(json.dumps(status, indent=2) + '\n')

    failed = [key for key, value in status.items() if value['status'] != 'passed']
    print(f'\n{len(status) - len(failed)}/{len(status)} steps passed. Status: {status_path}')
    print(f'Tables and figures: {run}/artifacts')
    for key in failed:
        print(f'  FAILED {key}: {status[key]["detail"]}')
    if failed:
        print(f'Rerun failed steps with: --resume {run.name}')
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
