#!/usr/bin/env python3
import json
from pathlib import Path
import sys

UNAVAILABLE = '0' * 16


def parse_events(lines):
    events = []
    for line in lines:
        start = line.find('IONREC {')
        if start >= 0:
            events.append(json.loads(line[start + len('IONREC '):]))
    return events


def read_events(directory):
    events = []
    for path in Path(directory).glob('trace*.moz_log'):
        with path.open(errors='replace') as log:
            events.extend(parse_events(log))
    return events


def summarize(events):
    compilations = sorted(
        (e for e in events if e['event'] == 'compile'
         and not e['self_hosted'] and not e['system']),
        key=lambda e: e['t_us'])
    if not compilations:
        raise ValueError('No guest Ion compilation records')
    versions = {c.get('schema', 1) for c in compilations}
    if len(versions) != 1 or not versions <= {1, 2}:
        raise ValueError('Mixed or unsupported Ion recurrence schemas')
    total = sum(c['backend_us'] for c in compilations)
    if not total:
        raise ValueError('No guest backend time recorded')
    result = {'compilations': len(compilations), 'backend_ms': total / 1000}
    for key in ('function', 'template'):
        seen = {}
        hit_us = 0
        hit_count = 0
        for c in compilations:
            if c[key] == UNAVAILABLE:
                raise ValueError(f'Unavailable {key} key; recurrence is incomplete')
            identity = c[key] if key == 'function' else (c['function'], c[key])
            instance = (c['pid'], c['script'])
            first, multiple = seen.get(identity, (instance, False))
            if first != instance or multiple:
                hit_us += c['backend_us']
                hit_count += 1
            seen[identity] = (first, multiple or first != instance)
        result[key + '_recurrence'] = hit_us / total
        result[key + '_recurrence_count'] = hit_count / len(compilations)
    templates = {}
    for compilation in compilations:
        templates.setdefault(compilation['function'], set()).add(compilation['template'])
    counts = {function: len(keys) for function, keys in sorted(templates.items())}
    # Fixed bins include zeros so Fossil can average distributions across runs.
    bins = dict.fromkeys(('1', '2', '3', '4', '5-8', '9-16', '17+'), 0)
    for count in counts.values():
        bucket = str(count) if count < 5 else ('5-8' if count <= 8 else
                                              '9-16' if count <= 16 else '17+')
        bins[bucket] += 1
    result['templates_per_function'] = counts
    result['template_multiplicity'] = {
        'functions': len(counts),
        'max': max(counts.values()),
        'shares': {key: count / len(counts) for key, count in bins.items()},
    }
    return result


def main():
    observation = json.load(sys.stdin)
    events = parse_events(observation['stdout'])
    if not events:
        run = json.loads(observation['stdout'][-1])
        events = read_events(run['directory'])
    print(json.dumps(summarize(events), indent=2))


if __name__ == '__main__':
    main()
