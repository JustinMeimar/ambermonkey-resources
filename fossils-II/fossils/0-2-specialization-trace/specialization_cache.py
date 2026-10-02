#!/usr/bin/env python3
"""Decode compilation feedback and separate entry profiles from Warp decisions."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


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
                _, marker, payload = line.partition('IONFEEDBACK\t')
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
                    if (*process(event), event['sequence']) != key:
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
        raise ValueError('no compilation feedback events; rebuild or enable specializationCache:4')


def projection(stub):
    fields = []
    unresolved = Counter()
    for field in stub['fields']:
        item = {'type': field['type']}
        if field['scalar']:
            item['value'] = field['bits']
        elif 'string' in field:
            item['string'] = field['string']
        else:
            if 'layout' in field:
                item['layout'] = field['layout']
            if field.get('function_identity_kind', 'unresolved') != 'unresolved':
                item['function'] = [field['function_identity_kind'], field['function_key']]
            # Descriptors characterize feedback; they do not resolve object identity,
            # closure environments, prototypes, or pointer-backed constants.
            item['unresolved'] = True
            unresolved[field['type']] += 1
        fields.append(item)
    return {'kind': stub['kind'], 'ir': stub['ir'], 'type_data': stub['type_data'],
            'fields': fields}, unresolved


def profile_sites(profile):
    structural, active = [], []
    unresolved = Counter()
    offsets = set()
    for site in profile['sites']:
        offset = site['offset']
        if offset in offsets:
            raise ValueError('duplicate IC site')
        offsets.add(offset)
        stubs, live = [], []
        for i, stub in enumerate(site['stubs']):
            projected, missing = projection(stub)
            unresolved.update(missing)
            stubs.append(projected)
            next_count = (site['stubs'][i + 1]['entered'] if i + 1 < len(site['stubs'])
                          else site['fallback_entered'])
            # Match Warp's uint32_t subtraction, including counter wraparound.
            successes = (stub['entered'] - next_count) % (1 << 32)
            if successes:
                live.append(projected)
        common = {'offset': offset, 'mode': site['mode'], 'has_failures': site['has_failures']}
        structural.append(dict(common, stubs=stubs))
        active.append(dict(common, stubs=live, fallback_active=bool(site['fallback_entered'])))
    if len(offsets) != profile['num_ic_entries']:
        raise ValueError('incomplete compilation-entry profile')
    return sorted(structural, key=lambda s: s['offset']), sorted(active, key=lambda s: s['offset']), unresolved


def read_recording(directory):
    scripts, compiles = {}, {}
    counts, seen, builds, processes, runs = Counter(), set(), set(), set(), set()
    interned = {}
    def intern(value):
        signature = digest(value)
        return signature, interned.setdefault(signature, value)
    with (directory / 'specialization.jsonl').open() as stream:
        for n, line in enumerate(stream, 1):
            event = json.loads(line)
            ident = (*process(event), event['sequence'])
            if ident in seen:
                raise ValueError(f'duplicate event {ident}')
            seen.add(ident)
            builds.add(event['build_id'])
            processes.add(process(event))
            runs.add(event['run'])
            kind = event['event']
            required = {'script': ('identity_kind',),
                        'profile': ('context', 'parent', 'sites', 'osr_offset')}.get(kind, ())
            if any(field not in event for field in required):
                raise ValueError(f'{directory}:{n}: incomplete {kind} schema; rebuild and record again')
            counts[kind] += 1
            if kind == 'script':
                owner = instance(event)
                if owner in scripts:
                    raise ValueError(f'duplicate script definition {owner}')
                scripts[owner] = event
            if not event.get('compilation') or kind in ('bailout', 'invalidate'):
                continue
            state = compiles.setdefault((*process(event), event['compilation']),
                                        {'contexts': {}, 'backend_us': 0, 'backend_samples': 0})
            if kind in ('ion_request', 'ion_link', 'dependencies'):
                if kind in state:
                    raise ValueError(f'duplicate {kind}')
                state[kind] = event
            elif kind == 'profile':
                context = event['context']
                if context in state['contexts']:
                    raise ValueError('duplicate profile context')
                if event['parent'] and event['parent'] not in state['contexts']:
                    raise ValueError('inline parent must precede child')
                state['contexts'][context] = {'profile': event, 'selected': {},
                                               'decisions': {}, 'types': {}}
            elif kind in ('selected', 'decision', 'polymorphic_types', 'profile_end'):
                context = state['contexts'].get(event['context'])
                if context is None:
                    raise ValueError('event without profile context')
                if kind == 'profile_end':
                    if 'end' in context:
                        raise ValueError('duplicate profile end')
                    context['end'] = event
                else:
                    field = {'selected': 'selected', 'decision': 'decisions',
                             'polymorphic_types': 'types'}[kind]
                    if event['offset'] in context[field]:
                        raise ValueError(f'duplicate {kind} at site')
                    context[field][event['offset']] = event
            elif kind == 'ion_compile':
                if event['phase'] == 'backend':
                    state['backend_us'] += event['duration_us']
                    state['backend_samples'] += 1
                elif event['phase'] == 'oracle':
                    state['oracle_success'] = event['success']
    if len(runs) != 1 or len(builds) != 1 or 'unspecified' in builds:
        raise ValueError('expected one run label and explicit build ID per recording')
    populations = {p: {'attempts': []} for p in ('guest', 'system', 'self_hosted')}
    for state in compiles.values():
        request = state.get('ion_request')
        if not request:
            raise ValueError('compilation event without request')
        owner = instance(request)
        if owner not in scripts:
            raise ValueError('undefined root script')
        if 'oracle_success' not in state:
            raise ValueError('compilation attempt without oracle outcome')
        script = scripts[owner]
        provenance = ('self_hosted' if script['self_hosted'] else
                      'system' if script['system_realm'] else 'guest')
        contexts = state['contexts']
        roots = [c for c, v in contexts.items() if not v['profile']['parent']]
        if len(roots) != 1:
            raise ValueError('expected exactly one root profile per compilation attempt')
        root_id = roots[0]
        if instance(contexts[root_id]['profile']) != owner:
            raise ValueError('root profile/request mismatch')
        children = defaultdict(list)
        for ident, context in contexts.items():
            profile = context['profile']
            if instance(profile) not in scripts:
                raise ValueError('undefined inline script')
            parent = profile['parent']
            if parent:
                if parent not in contexts or parent == ident:
                    raise ValueError('invalid inline parent')
                children[parent].append(ident)
        for context in contexts.values():
            profile_sites(context['profile'])
            site_offsets = {s['offset'] for s in context['profile']['sites']}
            if set(context['decisions']) - site_offsets:
                raise ValueError('decision at unknown IC site')
            if 'end' in context and any(e['decision'] == 'aborted' for e in context['decisions'].values()):
                raise ValueError('completed profile contains aborted decision')
        link = state.get('ion_link', {})
        success = link.get('success', False)
        if success and ('end' not in contexts[root_id] or not state.get('oracle_success')
                        or 'dependencies' not in state):
            raise ValueError('successful link without completed oracle')
        structural, active, unresolved = profile_sites(contexts[root_id]['profile'])
        structural_id, structural = intern(structural)
        active_id, active = intern(active)
        consumed_unresolved = Counter()
        visited = set()
        context_unresolved = Counter()
        def consumed(ident):
            context = contexts[ident]
            output = []
            for offset, event in sorted(context['decisions'].items()):
                decision = event['decision']
                selected = context['selected'].get(offset, {}).get('stubs', [])
                types = context['types'].get(offset, {}).get('types', [])
                if (decision in ('cacheir', 'inline')) != bool(selected):
                    raise ValueError('selected CacheIR/decision mismatch')
                if (decision == 'polymorphic_types') != bool(types):
                    raise ValueError('polymorphic type/decision mismatch')
                stubs = []
                for stub in selected:
                    value, missing = projection(stub)
                    stubs.append(value)
                    consumed_unresolved.update(missing)
                output.append({'offset': offset, 'decision': decision,
                               'stubs': stubs, 'types': types})
            if set(context['selected']) - set(context['decisions']):
                raise ValueError('selected CacheIR without decision')
            return output
        def tree(ident):
            if ident in visited:
                raise ValueError('cyclic inline contexts')
            visited.add(ident)
            context = contexts[ident]
            profile = context['profile']
            script = scripts[instance(profile)]
            output = consumed(ident)
            if script['identity_kind'] == 'unresolved':
                context_unresolved['script_identity'] += 1
            for snapshot in context.get('end', {}).get('snapshots', []):
                if snapshot['kind'] not in ('WarpBailout', 'WarpCacheIR', 'WarpInlinedCall', 'WarpPolymorphicTypes'):
                    context_unresolved['snapshot_payload:' + snapshot['kind']] += 1
            inline = []
            for child in children[ident]:
                child_context = contexts[child]
                offset = child_context['profile']['call_offset']
                decision = context['decisions'].get(offset, {}).get('decision')
                if decision == 'inline' and 'end' in child_context:
                    inline.append([offset, tree(child)])
            inline.sort(key=canonical)
            inline_offsets = [offset for offset, _ in inline]
            expected = [s['offset'] for s in output if s['decision'] == 'inline']
            if sorted(inline_offsets) != sorted(expected):
                raise ValueError('inline decision without exactly one completed child')
            return {'key': script['key'], 'identity_kind': script['identity_kind'],
                    'consumed': output, 'children': inline,
                    'history': [profile['failed_bounds_check'], profile['failed_lexical_check']],
                    'osr_offset': profile['osr_offset'],
                    'ic_hints': [[s['offset'], s['trial_inlining'], s['may_have_folded']]
                                 for s in profile['sites']],
                    'snapshots': context.get('end', {}).get('snapshots', [])}
        root_consumed = consumed(root_id) if 'end' in contexts[root_id] else None
        consumed_unresolved.clear()
        tree_value = tree(root_id) if state.get('oracle_success') else None
        context_unresolved['dependency_payloads'] += len(state.get('dependencies', {}).get('types', []))
        # Non-CacheIR snapshot payloads and dependency payloads are not yet normalized.
        row = {'key': script['key'] if script['identity_kind'] != 'unresolved' else None,
               'identity_kind': script['identity_kind'], 'success': success,
               'timestamp_us': request['timestamp_us'], 'sequence': request['sequence'],
               'entry': structural_id, 'active': active_id,
               'consumed': digest(root_consumed) if root_consumed is not None else None,
               'context': digest([tree_value, sorted(state.get('dependencies', {}).get('types', []))])
                          if tree_value is not None and 'dependencies' in state else None,
               'sites': structural, 'active_sites': active, 'consumed_sites': root_consumed,
               'unresolved_fields': dict(unresolved),
               'consumed_unresolved_fields': dict(consumed_unresolved),
               'context_unresolved': dict(context_unresolved),
               'inline_contexts': max(0, len(visited) - 1),
               'attempted_inline_contexts': len(contexts) - 1,
               'backend_us': state['backend_us'], 'backend_measured': bool(state['backend_samples']),
               'code_bytes': link.get('code_bytes', 0),
               'metadata_bytes': link.get('metadata_bytes', 0)}
        populations[provenance]['attempts'].append(row)
    for population in populations.values():
        population['attempts'].sort(key=lambda r: (r['timestamp_us'], r['sequence']))
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
