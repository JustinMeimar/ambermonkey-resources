#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import specialization_cache as sc

LABELS = ('train-a', 'train-b', 'evaluation')
LAYERS = ('entry', 'active', 'consumed', 'context')


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'percent': 100 * numerator / denominator if denominator else None}


def recurrence(training, evaluation, field, budget=None):
    variants = defaultdict(Counter)
    runs = defaultdict(set)
    for run, rows in enumerate(training):
        for row in rows:
            if row['key'] is None or row[field] is None:
                continue
            variants[row['key']][row[field]] += 1
            runs[row['key'], row[field]].add(run)
    selected = {}
    for key, profiles in variants.items():
        ranked = sorted(profiles, key=lambda v: (-len(runs[key, v]), -profiles[v], v))
        selected[key] = set(ranked if budget is None else ranked[:budget])
    eligible = [r for r in evaluation if r['key'] is not None and r[field] is not None]
    recurring = [r for r in eligible if r['key'] in selected]
    matched = [r for r in recurring if r[field] in selected[r['key']]]
    return {
        'training_keys': len(selected),
        'training_distinct_variants': sum(map(len, variants.values())),
        'selected_variants': sum(map(len, selected.values())),
        'variants_seen_in_every_training_run': sum(len(v) == len(training) for v in runs.values()),
        'eligible_evaluation_attempts': len(eligible),
        'unavailable_evaluation_attempts': len(evaluation) - len(eligible),
        'function_recurrence': fraction(len(recurring), len(eligible)),
        'profile_recurrence_given_function': fraction(len(matched), len(recurring)),
        'profile_recurrence_all_eligible': fraction(len(matched), len(eligible)),
        'matching_backend_work_all_attempts': fraction(sum(r['backend_us'] for r in matched),
                                                       sum(r['backend_us'] for r in evaluation)),
        'matched_entry_profiles_without_unresolved_fields': sum(not r['unresolved_fields'] for r in matched),
    }


def disagreement(a, b):
    left, right = ({s['offset']: s for s in sites} for sites in (a, b))
    reasons, offsets = Counter(), []
    for offset in sorted(left.keys() | right.keys()):
        x, y = left.get(offset), right.get(offset)
        if x == y:
            continue
        offsets.append(offset)
        if x is None or y is None:
            reasons['site_presence'] += 1
            continue
        for field in ('mode', 'has_failures', 'fallback_active', 'decision', 'types'):
            if x.get(field) != y.get(field):
                reasons[field] += 1
        xs, ys = x.get('stubs', []), y.get('stubs', [])
        if len(xs) != len(ys):
            reasons['chain_length'] += 1
        for sx, sy in zip(xs, ys):
            for field in ('kind', 'ir', 'type_data'):
                if sx[field] != sy[field]:
                    reasons[field] += 1
            if sx['fields'] != sy['fields']:
                reasons['stub_fields'] += 1
                for fx, fy in zip(sx['fields'], sy['fields']):
                    for field in ('type', 'value', 'layout', 'function', 'string'):
                        if fx.get(field) != fy.get(field):
                            reasons['field_' + field] += 1
    return offsets, reasons


def divergence(training, evaluation):
    candidates = defaultdict(dict)
    for rows in training:
        for row in rows:
            if row['key'] is not None:
                candidates[row['key']][row['entry']] = row
    reasons, distances = Counter(), Counter()
    examples = []
    mismatches = 0
    for row in evaluation:
        prior = candidates.get(row['key'], {})
        if not prior or row['entry'] in prior:
            continue
        mismatches += 1
        choices = []
        for signature, candidate in prior.items():
            offsets, why = disagreement(row['sites'], candidate['sites'])
            choices.append((len(offsets), signature, offsets, why))
        distance, signature, offsets, why = min(choices, key=lambda c: c[:2])
        reasons.update(why)
        distances[str(distance)] += 1
        if len(examples) < 40:
            examples.append({'key': row['key'], 'evaluation_profile': row['entry'],
                             'nearest_training_profile': signature,
                             'different_offsets': offsets, 'reasons': dict(why)})
    return {'mismatching_attempts_at_recurring_keys': mismatches,
            'different_site_count_histogram': dict(distances),
            'difference_occurrences': dict(reasons)}, examples


def transitions(training, evaluation, before, after):
    prior = defaultdict(set)
    for rows in training:
        for r in rows:
            if r['key'] is not None and r[before] is not None and r[after] is not None:
                prior[r['key'], r[before]].add(r[after])
    comparable = [r for r in evaluation if r[after] is not None
                  and (r['key'], r[before]) in prior]
    changed = [r for r in comparable if r[after] not in prior[r['key'], r[before]]]
    return fraction(len(changed), len(comparable))


def growth(recordings):
    previous, functions = set(), defaultdict(set)
    result = {}
    for label, rows in recordings:
        within = set()
        counters = Counter()
        for r in rows:
            if r['key'] is None:
                counters['unresolved_function'] += 1
                continue
            pair = r['key'], r['entry']
            if pair in previous:
                counters['seen_in_earlier_recording'] += 1
            elif pair in within:
                counters['repeat_first_seen_this_recording'] += 1
            else:
                counters['new_profile'] += 1
            within.add(pair)
            functions[r['key']].add(r['entry'])
        previous.update(within)
        result[label] = {**{k: counters[k] for k in ('new_profile', 'seen_in_earlier_recording',
                         'repeat_first_seen_this_recording', 'unresolved_function')},
                         'cumulative_profiles': len(previous),
                         'cumulative_functions': len(functions)}
    histogram = Counter(str(len(v)) for v in functions.values())
    return result, dict(histogram)


def analyze_paths(directories):
    metadata = [json.loads((d / 'run.json').read_text()) for d in directories]
    summaries = [json.loads((d / 'summary.json').read_text()) for d in directories]
    if len(directories) < 2:
        raise ValueError('need training and held-out evaluation recordings')
    if any(s['exit_code'] != 0 or not s.get('specialization_events', {}).get('profile') for s in summaries):
        raise ValueError('Expected complete compilation-feedback recordings')
    if len({m['build_id'] for m in metadata}) != 1:
        raise ValueError('Build differs between recordings')
    if any(m['environment'].get('JS_SPECIALIZATION_HINTS') for m in metadata):
        raise ValueError('Characterization requires default compilation thresholds')
    recordings = [sc.read_recording(d) for d in directories]
    seen_processes, seen_runs = set(), set()
    for recording in recordings:
        if recording['build_id'] != metadata[0]['build_id']:
            raise ValueError('Trace build differs from recording metadata')
        if seen_processes & recording['processes']:
            raise ValueError('Training/evaluation reuse the same process recording')
        if recording['run'] in seen_runs:
            raise ValueError('Duplicate recording label')
        seen_runs.add(recording['run'])
        seen_processes.update(recording['processes'])
    populations, details = {}, {}
    for provenance in ('guest', 'system', 'self_hosted'):
        rows = [r['populations'][provenance]['attempts'] for r in recordings]
        training, evaluation = rows[:-1], rows[-1]
        unresolved, context_unresolved = Counter(), Counter()
        for r in evaluation:
            unresolved.update(r['unresolved_fields'])
            context_unresolved.update(r['context_unresolved'])
        differences, examples = divergence(training, evaluation)
        curve, histogram = growth([(r['run'], population) for r, population in zip(recordings, rows)])
        linked_training = [[r for r in run if r['success']] for run in training]
        linked_evaluation = [r for r in evaluation if r['success']]
        populations[provenance] = {
            'evaluation_attempts': len(evaluation),
            'evaluation_successful_links': len(linked_evaluation),
            'evaluation_backend_us': sum(r['backend_us'] for r in evaluation),
            'attempts_with_backend_measurement': sum(r['backend_measured'] for r in evaluation),
            'unresolved_function_identities': sum(r['key'] is None for r in evaluation),
            'empty_entry_profiles': sum(not r['sites'] for r in evaluation),
            'entry_profiles_without_unresolved_fields': sum(not r['unresolved_fields'] for r in evaluation),
            'entry_unresolved_field_occurrences': dict(unresolved),
            'context_unresolved_occurrences': dict(context_unresolved),
            'attempts_with_inlining': sum(bool(r['inline_contexts']) for r in evaluation),
            'feedback_recurrence': {layer: recurrence(training, evaluation, layer) for layer in LAYERS},
            'successful_compilation_recurrence': {
                layer: recurrence(linked_training, linked_evaluation, layer) for layer in LAYERS},
            'concentration': {str(n): recurrence(training, evaluation, 'entry', n) for n in (1, 2, 4)},
            'new_consumed_given_recurring_entry': transitions(training, evaluation, 'entry', 'consumed'),
            'new_entry_given_recurring_consumed': transitions(training, evaluation, 'consumed', 'entry'),
            'new_context_given_recurring_consumed': transitions(training, evaluation, 'consumed', 'context'),
            'entry_divergence': differences,
            'entry_variants_per_function_histogram': histogram,
            'growth': curve,
        }
        by_key = defaultdict(lambda: {'entry': set(), 'active': set(), 'consumed': set(), 'context': set(),
                                     'attempts': 0, 'links': 0, 'backend_us': 0})
        for run in rows:
            for r in run:
                if r['key'] is None:
                    continue
                item = by_key[r['key']]
                for layer in LAYERS:
                    if r[layer] is not None:
                        item[layer].add(r[layer])
                item['attempts'] += 1
                item['links'] += r['success']
                item['backend_us'] += r['backend_us']
        details[provenance] = {'divergence_examples': examples, 'functions': {
            key: {name: len(value) if isinstance(value, set) else value for name, value in item.items()}
            for key, item in sorted(by_key.items())}}
    return {'build_id': metadata[0]['build_id'], 'recordings': metadata,
            'trace_summaries': summaries, 'populations': populations, 'details': details,
            'limits': [
                'Entry compares ordered IC chains and mode/failure state, excluding exact execution counts.',
                'Active compares cases with nonzero adjacent-count differences and fallback activity.',
                'Consumed compares recorded Warp IC choices, selected CacheIR and ordered polymorphic types.',
                'Context adds accepted inline topology, history flags, IC hints, snapshot kinds and dependency kinds.',
                'Runtime pointer values never participate; unresolved values remain explicitly counted.',
                'Function/shape descriptors are partial; closure environments, prototypes and other pointer-backed values remain unresolved.',
                'Non-CacheIR snapshot payloads and dependency payloads are not compared. Context is not a complete compiler-input identity.',
                'Self-hosted identities use bytecode and source coordinates within the exact engine build.',
                'Compilation attempts include failures; a separate view restricts both training and evaluation to successful links.',
                'Growth follows supplied recording order; this is not a bounded cache simulation or a navigation-level timeline.',
                'Compilation work is instrumented elapsed time, not saved wall time. No native code identity or speedup is inferred.',
            ]}


def analyze(directory):
    return analyze_paths([directory / label for label in LABELS])


def fossil_metrics(report):
    if any('feedback_recurrence' not in p for p in report['populations'].values()):
        raise ValueError('Recording lacks compilation-entry feedback; collect new measurements')
    def omit_undefined(value):
        if isinstance(value, dict):
            return {key: omit_undefined(item) for key, item in value.items()
                    if item is not None}
        return value

    return {'populations': omit_undefined({p: {k: v for k, v in metrics.items() if k != 'growth'}
                                           for p, metrics in report['populations'].items()})}


def main():
    if any(arg in sys.argv for arg in ('--directory', '--training', '--evaluation')):
        parser = argparse.ArgumentParser()
        parser.add_argument('--directory', type=Path)
        parser.add_argument('--training', type=Path, action='append')
        parser.add_argument('--evaluation', type=Path)
        args = parser.parse_args()
        if args.directory and not (args.training or args.evaluation):
            report = analyze(args.directory)
        elif args.training and args.evaluation and not args.directory:
            report = analyze_paths([*args.training, args.evaluation])
        else:
            parser.error('use --directory OR one or more --training plus --evaluation')
    else:
        observation = json.load(sys.stdin)
        records = [json.loads(line) for line in observation['stdout'] if line.strip()]
        reports = [r for r in records if r.get('event') == 'specialization_experiment']
        if len(reports) != 1:
            raise ValueError('Expected one completed specialization experiment')
        report = fossil_metrics(reports[0]['report'])
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
