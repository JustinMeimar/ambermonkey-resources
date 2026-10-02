#!/usr/bin/env python3
"""Decode framed traces and summarize the CacheIR selected by successful Ion builds."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

VERSION = 2
FORMAT = 'ion-recurrence-v2'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def process(event):
    return event['pid'], event['process_start_us']


def instance(event):
    return (*process(event), event['ic_script'])


def extract(logs, run):
    pending = {}
    seen = set()
    count = 0
    for path in logs:
        with open(path, encoding='utf-8') as stream:
            for line_no, line in enumerate(stream, 1):
                location = f'{path}:{line_no}'
                if 'SPCACHE\t' in line:
                    raise ValueError(f'{location}: legacy or lost trace record; rebuild the browser')
                _, marker, payload = line.partition('SPCACHE2\t')
                if not marker:
                    continue
                try:
                    pid, start, sequence, part, total, encoded = payload.split()
                    key = tuple(map(int, (pid, start, sequence)))
                    part, total = int(part), int(total)
                    if not 0 <= part < total <= 1_000_000 or key in seen:
                        raise ValueError('invalid or duplicate frame')
                    data = bytes.fromhex(encoded)
                    if not 0 < len(data) <= 512:
                        raise ValueError('invalid frame size')
                    expected, pieces = pending.setdefault(key, (total, {}))
                    if expected != total or part in pieces:
                        raise ValueError('duplicate or inconsistent frame')
                    pieces[part] = data
                    if len(pieces) != total:
                        continue
                    event = json.loads(b''.join(pieces[i] for i in range(total)))
                    if event['version'] != VERSION or (*process(event), event['sequence']) != key:
                        raise ValueError('frame/event identity mismatch')
                    del pending[key]
                    seen.add(key)
                    count += 1
                    event['run'] = run
                    yield event
                except (ValueError, KeyError, TypeError) as error:
                    raise ValueError(f'{location}: {error}') from error
    if pending:
        raise ValueError(f'incomplete trace: {len(pending)} unfinished records; first ID {next(iter(pending))}')
    if not count:
        raise ValueError('no v2 specialization events; rebuild or enable specializationCache:4')


def projection(stub):
    return {'kind': stub['kind'], 'ir': stub['ir'], 'type_data': stub['type_data'],
            'fields': [{'type': f['type'], 'bits': f['bits'] if f['scalar'] else None,
                        'layout': f.get('layout')} for f in stub['fields']]}


def read_recording(directory):
    scripts = {}
    compiles = defaultdict(lambda: {'profiles': [], 'selected': defaultdict(list),
                                   'backend_us': 0, 'obstacles': Counter()})
    counts = Counter()
    seen = set()
    builds = set()
    processes = set()
    runs = set()
    with (directory / 'specialization.jsonl').open() as stream:
        for n, line in enumerate(stream, 1):
            event = json.loads(line)
            if event.get('version') != VERSION:
                raise ValueError(f'{directory}:{n}: expected v2 event')
            ident = (*process(event), event['sequence'])
            if ident in seen:
                raise ValueError(f'duplicate event {ident}')
            seen.add(ident)
            builds.add(event['build_id'])
            processes.add(process(event))
            runs.add(event['run'])
            kind = event['event']
            counts[kind] += 1
            if kind == 'script':
                owner = instance(event)
                if owner in scripts:
                    raise ValueError(f'duplicate script definition {owner}')
                scripts[owner] = event
            if not event.get('compilation'):
                continue
            state = compiles[(*process(event), event['compilation'])]
            if kind in ('ion_request', 'ion_link'):
                if kind in state:
                    raise ValueError(f'duplicate {kind} for {ident}')
                state[kind] = event
            elif kind == 'profile':
                state['profiles'].append(instance(event))
            elif kind == 'selected':
                owner = instance(event)
                state['selected'][owner].append([event['offset'], [projection(s) for s in event['stubs']]])
                for stub in event['stubs']:
                    state['obstacles'].update(f['type'] for f in stub['fields'] if not f['scalar'])
            elif kind == 'dependencies':
                state['dependencies'] = sorted(event['types'])
            elif kind == 'ion_compile' and event['phase'] == 'backend':
                state['backend_us'] += event['duration_us']
    if len(runs) != 1:
        raise ValueError('expected one run label per recording')
    if len(builds) != 1 or 'unspecified' in builds:
        raise ValueError('expected one explicit build ID per recording')
    populations = {p: {'requests': 0, 'backend_us': 0, 'linked': [],
                       'missing_source_links': 0} for p in ('guest', 'system', 'self_hosted')}
    for state in compiles.values():
        request = state.get('ion_request')
        if not request:
            raise ValueError('compilation event without request')
        owner = instance(request)
        if owner not in scripts or any(i not in scripts for i in state['profiles']):
            raise ValueError('undefined script identity')
        script = scripts[owner]
        provenance = ('self_hosted' if script['self_hosted'] else
                      'system' if script['system_realm'] else 'guest')
        population = populations[provenance]
        population['requests'] += 1
        population['backend_us'] += state['backend_us']
        link = state.get('ion_link', {})
        if not link.get('success'):
            continue
        if owner not in state['profiles'] or 'dependencies' not in state:
            raise ValueError('successful link without root snapshot or dependencies')
        if any(i not in state['profiles'] for i in state['selected']):
            raise ValueError('selected CacheIR without snapshot')
        root = sorted(state['selected'][owner], key=canonical)
        profiles = [[scripts[i]['key'], sorted(state['selected'][i], key=canonical)]
                    for i in state['profiles']]
        complete_sources = all(scripts[i]['source_encoding'] for i in state['profiles'])
        if not script['source_encoding']:
            population['missing_source_links'] += 1
        population['linked'].append({
            'key': script['key'] if script['source_encoding'] else None,
            'root': digest(root) if root else None,
            'snapshot': digest([sorted(profiles, key=canonical), state['dependencies']])
                        if root and complete_sources else None,
            'inline_profiles': len(state['profiles']) - 1,
            'opaque_fields': dict(state['obstacles']),
            'backend_us': state['backend_us'], 'code_bytes': link['code_bytes'],
            'metadata_bytes': link['metadata_bytes'],
        })
    return {'build_id': next(iter(builds)), 'counts': dict(counts), 'populations': populations,
            'processes': processes, 'run': next(iter(runs))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['extract'])
    parser.add_argument('--run', required=True)
    parser.add_argument('logs', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        for event in extract(args.logs, args.run):
            print(json.dumps(event, separators=(',', ':')))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
