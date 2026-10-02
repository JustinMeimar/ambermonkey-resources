#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys

import specialization_cache as sc

LABELS = ('train-a', 'train-b', 'evaluation')


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'percent': 100 * numerator / denominator if denominator else None}


def recurrence(training, evaluation, field, budget):
    variants = defaultdict(lambda: defaultdict(list))
    runs = defaultdict(set)
    for run, rows in enumerate(training):
        for row in rows:
            if row['key'] is None or row[field] is None:
                continue
            key = row['key'], row[field]
            variants[row['key']][row[field]].append(row)
            runs[key].add(run)
    selected = {}
    for key, versions in variants.items():
        ranked = sorted(versions, key=lambda v: (-len(runs[key, v]), -len(versions[v]), v))
        selected[key] = ranked[:budget]
    eligible = [row for row in evaluation if row['key'] is not None and row[field] is not None]
    matched = [row for row in eligible if row[field] in selected.get(row['key'], [])]
    return {
        'training_keys': len(selected),
        'training_distinct_variants': sum(map(len, variants.values())),
        'stored_variants': sum(map(len, selected.values())),
        'variants_seen_in_both_training_runs': sum(len(v) == 2 for v in runs.values()),
        'eligible_evaluation_links': len(eligible),
        'matching_evaluation_links': fraction(len(matched), len(eligible)),
        'matching_backend_work': fraction(sum(r['backend_us'] for r in matched),
                                          sum(r['backend_us'] for r in eligible)),
        'sum_variant_median_code_bytes': sum(statistics.median(r['code_bytes'] for r in variants[k][v])
                                             for k, vs in selected.items() for v in vs),
    }


def analyze(directory):
    metadata = [json.loads((directory / label / 'run.json').read_text()) for label in LABELS]
    summaries = [json.loads((directory / label / 'summary.json').read_text()) for label in LABELS]
    if any(s['exit_code'] != 0 or s.get('trace_version') != sc.VERSION for s in summaries):
        raise ValueError('Expected three complete v2 traced recordings')
    if len({m['build_id'] for m in metadata}) != 1 or len({m['workload'] for m in metadata}) != 1:
        raise ValueError('Build or workload differs between recordings')
    if any(m['environment'].get('JS_SPECIALIZATION_HINTS') for m in metadata):
        raise ValueError('Characterization requires default compilation thresholds')
    recordings = [sc.read_recording(directory / label) for label in LABELS]
    if any(r['build_id'] != metadata[0]['build_id'] for r in recordings):
        raise ValueError('Trace build differs from recording metadata')
    seen_processes = set()
    for label, recording, meta in zip(LABELS, recordings, metadata):
        if recording['run'] != f"{meta['workload']}-{label}":
            raise ValueError('Trace run label differs from recording role')
        if seen_processes & recording['processes']:
            raise ValueError('Training/evaluation reuse the same process recording')
        seen_processes.update(recording['processes'])
    populations = {}
    for provenance in ('guest', 'system', 'self_hosted'):
        train = [r['populations'][provenance]['linked'] for r in recordings[:2]]
        evaluation = recordings[2]['populations'][provenance]
        links = evaluation['linked']
        keys = [{r['key'] for r in rows if r['key'] is not None} for rows in train]
        eligible = [r for r in links if r['key'] is not None]
        both = keys[0] & keys[1]
        obstacles = Counter()
        for row in links:
            obstacles.update(row['opaque_fields'])
        populations[provenance] = {
            'evaluation_ion_requests': evaluation['requests'],
            'evaluation_successful_links': len(links),
            'requests_without_successful_link': evaluation['requests'] - len(links),
            'evaluation_backend_us': evaluation['backend_us'],
            'missing_source_links': evaluation['missing_source_links'],
            'links_without_root_selected_cacheir': sum(r['root'] is None for r in eligible),
            'evaluation_unique_content_keys': len({r['key'] for r in eligible}),
            'keys_compiled_in_both_training_runs': len(both),
            'evaluation_links_at_recurring_keys': fraction(sum(r['key'] in both for r in eligible), len(eligible)),
            'evaluation_links_with_inlinees': sum(bool(r['inline_profiles']) for r in links),
            'evaluation_opaque_field_occurrences': dict(obstacles),
            'projection_recurrence': {
                field: {str(budget): recurrence(train, links, field, budget) for budget in (1, 2, 4)}
                for field in ('root', 'snapshot')},
        }
    return {'format': sc.FORMAT, 'build_id': metadata[0]['build_id'],
            'recordings': metadata, 'trace_summaries': summaries, 'populations': populations,
            'selection': 'Training run frequency, then compilation frequency, then signature; frozen before evaluation.',
            'limits': [
                'Unit: successful local Ion compilation, not function invocation or hypothetical cache installation.',
                'Root compares selected CacheIR, scalar bits and recorded shape layouts; process-local pointers are erased.',
                'Snapshot additionally compares an unordered multiset of inlinee profiles and dependency types; call topology is not encoded.',
                'Opaque objects, symbols, prototypes, constants, shape lists and optimizer guards remain unresolved.',
                'Non-CacheIR Warp snapshots and polymorphic type-data specializations are not compared.',
                'Matching projections are neither native-code identity nor evidence that transferred code would execute safely.',
                'No lifetime survival, first-conflict timing, entry-time selection or performance benefit is measured.',
                'No-selected-root and missing-source compilations are excluded explicitly from projection denominators.',
                'Backend durations include instrumentation effects and concurrent work; storage estimates exclude rebinding costs.',
                'Repeated benchmark inputs characterize recurrence on those inputs, not cross-site generalization.',
            ]}


def main():
    if '--directory' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--directory', type=Path, required=True)
        report = analyze(parser.parse_args().directory)
    else:
        observation = json.load(sys.stdin)
        records = [json.loads(line) for line in observation['stdout'] if line.strip()]
        reports = [r for r in records if r.get('event') == 'specialization_experiment']
        if len(reports) != 1:
            raise ValueError('Expected one completed specialization experiment')
        report = reports[0]['report']
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
