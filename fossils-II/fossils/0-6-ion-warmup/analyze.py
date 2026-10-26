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


def predictions(training):
    templates = defaultdict(lambda: defaultdict(int))
    for r in training:
        if r['outcome'] == 'installed':
            templates[r['function']][r['template']] += 1
    return {function: [t for t, _ in sorted(counts.items(), key=lambda c: -c[1])]
            for function, counts in templates.items()}


def total(parts):
    result = defaultdict(float)
    for part in parts:
        for key, value in part.items():
            result[key] += value
    return dict(result)


def lower(function):
    return total(function['lower'][tier] for tier in replay.LOWER_TIERS)


def breakdown(chosen):
    return {
        'functions': len(chosen),
        'lower': total(lower(f) for f in chosen),
        'tiers': {tier: total(f['lower'][tier] for f in chosen)
                  for tier in replay.LOWER_TIERS},
        'phases': {phase: total(f['phases'][phase] for f in chosen)
                   for phase in replay.PHASES},
    }


# Ion speeds up only the JS itself; native callees run the same either way.
def by_class(functions, pool):
    result = {cls: breakdown([f for f in functions if f['classes'][pool] == cls])
              for cls in CLASSES}
    exact = result['exact']['lower'].get('js_code_ms', 0)
    result['scaled_exact_js_code_ms'] = {f'speedup_{s}': exact * (1 - 1 / s)
                                      for s in SPEEDUPS}
    return result


# Feedback-phase time is removable only if the template is chosen at first sight,
# before any feedback: from the training session's k most frequent templates.
def predicted(functions, ranked):
    result = {}
    for k in (1, 2):
        chosen = [f for f in functions
                  if f['template'] in ranked.get(f['function'], [])[:k]]
        result[f'top{k}'] = breakdown(chosen)
    return result


def main():
    observation = json.load(sys.stdin)
    report = json.loads(observation['stdout'][-1])
    if report['schema'] != 7:
        raise ValueError('Expected schema 7 capture')
    directory = Path(report['directory'])
    evaluation, invalid = guest(directory, 'evaluation')
    training, _ = guest(directory, 'training')
    pools = {
        'runtime': replay.classify(evaluation, scope='runtime'),
        'session': replay.classify(evaluation, scope='shared'),
        'training': replay.classify(evaluation, training=training, scope='shared'),
    }
    default = max(r['ion_threshold'] for r in evaluation)
    hinted = sum(r['ion_threshold'] != default for r in evaluation)
    threads = replay.read_profile(directory / 'evaluation/profile.json')
    result = replay.warmup(evaluation, threads, pools)
    functions = result['functions']
    tiers = defaultdict(list)
    for thread in result['threads'].values():
        for tier, totals in thread['tiers'].items():
            tiers[tier].append(totals)
    metrics = {
        'functions': len(functions),
        'invalid_key_requests': invalid,
        'ion_threshold': default,
        'hinted_threshold_requests': hinted,
        'predicted': predicted(functions, predictions(training)),
        'excluded_requests': result['excluded'],
        'max_process_start_skew_us': result['max_process_start_skew_us'],
        'thread_tiers': {tier: total(parts) for tier, parts in tiers.items()},
        'no_realm_js_ms': sum(t['no_realm_js_ms'] for t in result['threads'].values()),
        'attributed_lower': total(lower(f) for f in functions),
        'inlined_in_ion': total(f['inlined_in_ion'] for f in functions),
        'after_install_lower': total(f['after_install']['lower'] for f in functions),
        'pools': {pool: by_class(functions, pool) for pool in pools},
        'function_rows': functions,
    }
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
