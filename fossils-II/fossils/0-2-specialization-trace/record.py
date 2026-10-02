#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
from browser_workloads import TESTS


def main():
    workload = sys.argv[1]
    if workload not in TESTS:
        raise ValueError(f'Unknown workload: {workload}')
    root = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox'))
    output = root / 'artifacts/specialization-browser/fossil-runs' / uuid.uuid4().hex
    output.mkdir(parents=True)
    shutil.copytree(HERE, output / 'fossil', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(HERE.parent / 'common', output / 'common',
                    ignore=shutil.ignore_patterns('__pycache__'))
    checksums = {
        str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ('fossil', 'common')
        for path in sorted((output / folder).rglob('*')) if path.is_file()
    }
    (output / 'SHA256SUMS.json').write_text(json.dumps(checksums, indent=2) + '\n')
    for step, label in enumerate(('train-a', 'train-b', 'evaluation'), 1):
        print(f'[{workload}] Recording {step}/3: {label}', file=sys.stderr, flush=True)
        result = subprocess.run([sys.executable, str(output / 'fossil/capture.py'), workload,
                                 '--run', label, '--output', str(output)], stdout=sys.stderr)
        if result.returncode:
            raise SystemExit(f'{workload}/{label} failed (exit {result.returncode}). '
                             f'Incomplete experiment; logs: {output / workload / label / "harness.log"}')
    print(f'[{workload}] Analyzing feedback recurrence and site divergence', file=sys.stderr, flush=True)
    result = subprocess.check_output(
        [sys.executable, str(output / 'fossil/analyze.py'), '--directory',
         str(output / workload)], text=True)
    report = json.loads(result)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'event': 'specialization_experiment', 'workload': workload,
                      'raw_directory': str(output), 'report': report}))


if __name__ == '__main__':
    main()
