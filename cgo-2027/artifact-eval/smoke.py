#!/usr/bin/env python3
"""Run the verified single-variant smoke paths sequentially in the container."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PLAN = [
    ('0-0-static-tables', None, []),
    ('6-1-corpus-construction', 'amazon', []),
    ('7-6-binary-size', None, []),
    ('7-2-ambermonkey-perf-octane', 'default', []),
    ('7-2-ambermonkey-perf-s3', 'default', []),
    ('7-2-oracle-corpus', 'speedometer3-aot-only', ['speedometer3']),
    ('7-1-corpus-coverage', 'speedometer3', ['baseline-function-table']),
    ('7-4-artifact-installation-startup', 'default-no-ion', []),
    ('7-4-artifact-installation-cost', 'default-no-ion', ['attachment']),
    ('7-6-cross-process-memory-sharing', 'default', ['aggregate']),
    ('7-5-indirection-e2e-s3', 'default-no-ion', ['perf']),
    ('7-3-v8-jitless-comparison', 'speedometer-v8-jitless', []),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', action='append', choices=[entry[0] for entry in PLAN])
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error('--timeout must be positive')
    selected = [entry for entry in PLAN if not args.only or entry[0] in args.only]
    if args.list:
        for name, variant, artifacts in selected:
            print(f'{name}: {variant or "static artifacts"}; artifacts={artifacts}')
        return
    results = Path(os.environ.get('AMBERMONKEY_RESULTS', '/results'))
    results.mkdir(parents=True, exist_ok=True)
    summary_path = results / f'smoke-{time.time_ns()}.json'
    summary = {'started_unix': time.time(), 'status': 'running',
               'iterations': 1, 'timeout_seconds': args.timeout,
               'dry_run': args.dry_run, 'experiments': []}

    def save():
        temporary = summary_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(summary, indent=2) + '\n')
        temporary.replace(summary_path)

    save()
    print(f'Suite status: {summary_path}', flush=True)
    for name, variant, artifacts in selected:
        command = [sys.executable, str(Path(__file__).with_name('run.py')),
                   name, '-n', '1', '--timeout', str(args.timeout)]
        if variant:
            command.extend(['--variant', variant])
        for artifact in artifacts:
            command.extend(['--artifact', artifact])
        if args.dry_run:
            command.append('--dry-run')
        entry = {'experiment': name, 'variant': variant, 'status': 'running'}
        summary['experiments'].append(entry)
        save()
        print(f'[{len(summary["experiments"])}/{len(selected)}] {name}', flush=True)
        started = time.monotonic()
        result = subprocess.run(command)
        entry.update(status=('previewed' if args.dry_run else 'passed')
                     if result.returncode == 0 else 'failed',
                     exit_code=result.returncode,
                     duration_seconds=time.monotonic() - started)
        save()
    summary['status'] = 'failed' if any(e['status'] == 'failed' for e in summary['experiments']) else ('previewed' if args.dry_run else 'passed')
    save()
    print(f'Suite {summary["status"]}: {summary_path}', flush=True)
    return int(summary['status'] == 'failed')


if __name__ == '__main__':
    raise SystemExit(main())
