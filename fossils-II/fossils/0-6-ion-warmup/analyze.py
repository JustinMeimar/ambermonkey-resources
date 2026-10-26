#!/usr/bin/env python3
"""Attribute sampled lower-tier execution to Ion compilations and template sets."""
from collections import defaultdict
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox')).resolve()
spec = importlib.util.spec_from_file_location('ion_recurrence', ROOT / 'js/src/jit/ion_recurrence.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

SPEEDUPS = (3, 10)
CLASSES = ('exact', 'function', 'new')


def guest(directory, phase):
    records, _ = replay.read_traces(sorted((directory / phase).glob('trace*.moz_log')))
    records = [r for r in records if not r['system'] and not r['self_hosted']]
    return [r for r in records if r['key_valid']], sum(not r['key_valid'] for r in records)


def lower(function, unit):
    return sum(function['lower'][tier][unit] for tier in replay.LOWER_TIERS)


def by_class(functions, pool):
    result = {}
    for cls in CLASSES:
        chosen = [f for f in functions if f['classes'][pool] == cls]
        result[cls] = {
            'functions': len(chosen),
            'lower_ms': sum(lower(f, 'ms') for f in chosen),
            'lower_cpu_ms': sum(lower(f, 'cpu_ms') for f in chosen),
            'tiers_ms': {tier: sum(f['lower'][tier]['ms'] for f in chosen)
                         for tier in replay.LOWER_TIERS},
            'phases_ms': {phase: sum(f['phases'][phase]['ms'] for f in chosen)
                          for phase in replay.PHASES},
        }
    exact = result['exact']['lower_ms']
    result['scaled_exact_ms'] = {f'speedup_{s}': exact * (1 - 1 / s) for s in SPEEDUPS}
    return result


def main():
    observation = json.load(sys.stdin)
    report = json.loads(observation['stdout'][-1])
    if report['schema'] != 6:
        raise ValueError('Expected schema 6 capture')
    directory = Path(report['directory'])
    evaluation, invalid = guest(directory, 'evaluation')
    training, _ = guest(directory, 'training')
    pools = {
        'runtime': replay.classify(evaluation, scope='runtime'),
        'session': replay.classify(evaluation, scope='shared'),
        'training': replay.classify(evaluation, training=training, scope='shared'),
    }
    threads = replay.read_profile(directory / 'evaluation/profile.json')
    result = replay.warmup(evaluation, threads, pools)
    functions = result['functions']
    context = defaultdict(lambda: {'ms': 0, 'cpu_ms': 0})
    for thread in result['threads'].values():
        for tier, totals in thread['tiers'].items():
            context[tier]['ms'] += totals['ms']
            context[tier]['cpu_ms'] += totals['cpu_ms']
    metrics = {
        'functions': len(functions),
        'invalid_key_requests': invalid,
        'excluded_requests': result['excluded'],
        'max_process_start_skew_us': result['max_process_start_skew_us'],
        'thread_tiers': dict(context),
        'attributed_lower_ms': sum(lower(f, 'ms') for f in functions),
        'ion_before_install_ms': sum(f['ion_before_install']['ms'] for f in functions),
        'after_install_lower_ms': sum(f['after_install']['lower']['ms'] for f in functions),
        'pools': {pool: by_class(functions, pool) for pool in pools},
        'function_rows': functions,
    }
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
