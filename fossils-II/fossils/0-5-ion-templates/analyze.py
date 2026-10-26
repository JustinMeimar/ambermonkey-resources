#!/usr/bin/env python3
"""Reduce a capture's raw traces to the recurrence metrics used for analysis."""
from collections import Counter, defaultdict
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox')).resolve()
spec = importlib.util.spec_from_file_location('ion_recurrence', ROOT / 'js/src/jit/ion_recurrence.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def fraction(part, whole):
    return part / whole if whole else 0


# Donor pools: earlier in the same runtime, earlier anywhere in the evaluation
# session, and every installation from the training session.
def pools(evaluation, training):
    return {
        'runtime': replay.analyze(evaluation, scope='runtime'),
        'session': replay.analyze(evaluation, scope='shared'),
        'training': replay.analyze(evaluation, training=training, scope='shared'),
    }


def guest_metrics(evaluation, training):
    cpu = sum(max(r['backend_cpu_us'], 0) for r in evaluation)
    metrics = {'requests': len(evaluation), 'backend_cpu_ms': cpu / 1000}
    for name, report in pools(evaluation, training).items():
        totals = report['totals']
        hit_cpu = sum(t.get('hit_backend_cpu_us', 0) for t in report['by_thread'].values())
        metrics[f'{name}_hit_fraction'] = fraction(totals['candidate_hits'], len(evaluation))
        metrics[f'{name}_hit_cpu_fraction'] = fraction(hit_cpu, cpu)
        metrics[f'{name}_identity_only_fraction'] = fraction(
            totals.get('identity_only_hits', 0), len(evaluation))
    templates = defaultdict(Counter)
    for r in evaluation:
        templates[r['function']][r['template']] += 1
    for k in (1, 2):
        covered = sum(c for t in templates.values() for _, c in t.most_common(k))
        metrics[f'top{k}_template_coverage'] = fraction(covered, len(evaluation))
    fingerprint = sum(r['described_us'] - r['ready_us'] for r in evaluation if r['ready_us'])
    metrics['fingerprint_overhead'] = fraction(fingerprint, cpu)
    return metrics


def self_hosted_metrics(evaluation, training):
    metrics = {'self_hosted_requests': len(evaluation)}
    reports = pools(evaluation, training)
    for name in ('session', 'training'):
        totals = reports[name]['totals']
        metrics[f'self_hosted_{name}_hit_fraction'] = fraction(
            totals['candidate_hits'], len(evaluation))
        metrics[f'self_hosted_{name}_identity_only_fraction'] = fraction(
            totals.get('identity_only_hits', 0), len(evaluation))
    return metrics


def main():
    observation = json.load(sys.stdin)
    report = json.loads(observation['stdout'][-1])
    if report['schema'] != 5:
        raise ValueError('Expected schema 5 capture')
    directory = Path(report['directory'])
    phases = {}
    for phase in ('training', 'evaluation'):
        records, _ = replay.read_traces(sorted((directory / phase).glob('trace*.moz_log')))
        records = [r for r in records if not r['system']]
        invalid = sum(not r['key_valid'] for r in records)
        records = [r for r in records if r['key_valid']]
        phases[phase] = {'invalid': invalid} | {
            kind: [r for r in records if bool(r['self_hosted']) == hosted]
            for kind, hosted in (('guest', False), ('self_hosted', True))}
    training, evaluation = phases['training'], phases['evaluation']
    metrics = guest_metrics(evaluation['guest'], training['guest'])
    metrics.update(self_hosted_metrics(evaluation['self_hosted'], training['self_hosted']))
    metrics['invalid_key_requests'] = evaluation['invalid']
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
