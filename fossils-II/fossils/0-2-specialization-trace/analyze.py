#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
import contextlib
import io
import json
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace

import specialization_cache as sc


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'percent': 100 * numerator / denominator if denominator else None}


def distribution(values):
    return {'n': len(values), 'min': min(values) if values else None,
            'median': statistics.median(values) if values else None,
            'max': max(values) if values else None}


def baseline_population(directories, evaluation):
    training_keys = set()
    installs = []
    for directory in directories:
        with (directory / 'baseline.jsonl').open() as stream:
            for line in stream:
                event = json.loads(line)
                if (event['event'] != 'install' or event['provenance'] != 'guest'
                        or not event['key_has_source']):
                    continue
                if directory.name == 'evaluation':
                    installs.append(event)
                else:
                    training_keys.add(tuple(event['cache_key']))
    pointers = defaultdict(list)
    for event in installs:
        pointers[event['pid'], int(event['script'], 16)].append(event)
    bridges = defaultdict(list)
    for event in evaluation:
        if event['event'] == 'baseline_install':
            bridges[event['pid'], int(event['script'], 16)].append(event)
    joined = []
    unmatched = 0
    for pointer, entries in pointers.items():
        matches = bridges[pointer]
        if len(matches) != len(entries) or len({sc.process(e) for e in matches}) != 1:
            unmatched += len(entries)
            continue
        for install, bridge in zip(sorted(entries, key=lambda e: e['timestamp_us']),
                                   sorted(matches, key=lambda e: e['sequence'])):
            joined.append((install, sc.instance(bridge)))
    recurring = [(e, ident) for e, ident in joined if tuple(e['cache_key']) in training_keys]
    return {
        'guest_evaluation_installs': len(installs),
        'guest_evaluation_unique_keys': len({tuple(e['cache_key']) for e in installs}),
        'installs_at_training_baseline_keys': sum(tuple(e['cache_key']) in training_keys for e in installs),
        'joined_installs': len(joined), 'unmatched_installs': unmatched,
        'baseline_cache_bytes_per_install': distribution([e['cache_bytes'] for e in installs]),
    }, recurring


def analyze(directory):
    directories = [directory / label for label in ('train-a', 'train-b', 'evaluation')]
    metadata = [json.loads((d / 'run.json').read_text()) for d in directories]
    summaries = [json.loads((d / 'summary.json').read_text()) for d in directories]
    if any(s['exit_code'] != 0 for s in summaries):
        raise ValueError('Cannot analyze a failed recording')
    if len({m['build_id'] for m in metadata}) != 1:
        raise ValueError('Browser changed between recordings')
    if any(m['environment'].get('JS_SPECIALIZATION_HINTS') for m in metadata):
        raise ValueError('Characterization requires default compilation thresholds')
    paths = [d / 'specialization.jsonl' for d in directories]
    events = sc.read_events([paths[2]])
    scripts, compiles, histories = sc.collect(events)
    baseline, recurring = baseline_population(directories, events)
    populations = {}
    for provenance in ('guest', 'system', 'self_hosted'):
        eligible = {ident for ident, script in scripts.items()
                    if not script['inlined'] and sc.eligible(script, provenance)}
        owned = [c for c in compiles.values()
                 if c.get('request') and sc.instance(c['request']) in eligible]
        linked = [c for c in owned if c.get('link', {}).get('success')]
        backend = sum(p['duration_us'] for c in owned for p in c['phases'] if p['phase'] == 'backend')
        population = {
            'eligible_lifetimes': len(eligible),
            'unique_content_keys': len({scripts[i]['key'] for i in eligible}),
            'ion_requests': len(owned), 'successful_ion_links': len(linked),
            'requests_without_successful_link': len(owned) - len(linked),
            'local_bailouts': sum(e['event'] == 'bailout' for i in eligible for e in histories[i]),
            'local_invalidations': sum(e['event'] == 'invalidate' for i in eligible for e in histories[i]),
            'lifetimes_without_end': sum(not any(e['event'] == 'end' for e in histories[i]) for i in eligible),
            'evaluation_backend_us': backend,
            'ion_code_bytes_per_link': distribution([c['link']['code_bytes'] for c in linked]),
            'budgets': {},
        }
        for budget in (1, 2, 4):
            manifest_path = directory / f'manifest-{provenance}-{budget}.json'
            sc.train(SimpleNamespace(traces=paths[:2], provenance=provenance, min_runs=2,
                                     variants=budget, output=manifest_path, hints=None))
            manifest = json.loads(manifest_path.read_text())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                sc.evaluate(SimpleNamespace(manifest=manifest_path, traces=[paths[2]]))
            transfer = json.loads(output.getvalue())
            (directory / f'transfer-{provenance}-{budget}.json').write_text(output.getvalue())
            counts = transfer['counts']
            matched = counts.get('training_key_matches', 0)
            versions = [v for vs in manifest['scripts'].values() for v in vs]
            obstacles = Counter()
            dependencies = Counter()
            for variant in versions:
                obstacles.update(variant['obstacles'])
                dependencies.update(map(str, variant['dependencies']))
            rows = transfer['instances']
            result = {
                'counts': counts,
                'training_keys_with_selected_projection': len(manifest['scripts']),
                'training_recurring_ion_keys': len(manifest['hint_keys']),
                'stored_variants': len(versions),
                'sum_variant_median_ion_code_bytes': sum(v['code_bytes_median'] for v in versions),
                'matched_lifetime_coverage': fraction(matched, len(eligible)),
                'first_variant_no_observed_conflict': fraction(counts.get('first_variant_no_observed_conflict', 0), matched),
                'any_variant_no_observed_conflict': fraction(counts.get('any_variant_no_observed_conflict', 0), matched),
                'any_variant_all_sites_observed_without_conflict': fraction(counts.get('any_variant_all_selected_sites_observed', 0), matched),
                'work_weights': transfer['work_weights'],
                'backend_work_at_fully_observed_survivors': fraction(transfer['work_weights'].get('backend_us_at_projection_survivors', 0), backend),
                'first_variant_conflict_warmup': distribution([
                    conflict['warmup'] for row in rows for conflict in row['conflicts']
                    if conflict['variant'] == manifest['scripts'][row['key']][0]['id']
                    and conflict['warmup'] is not None]),
                'variants_with_inlining': sum(bool(v['inline_keys']) for v in versions),
                'dependency_types_per_stored_variant': dict(dependencies),
                'training_obstacle_occurrences': dict(obstacles),
            }
            if provenance == 'guest':
                by_instance = {tuple(row['instance']): row for row in rows}
                covered = [(e, by_instance[i]) for e, i in recurring if i in by_instance]
                result['baseline_recurring_install_projection_coverage'] = fraction(len(covered), len(recurring))
                result['baseline_recurring_installs_with_fully_observed_survivor'] = fraction(
                    sum(bool(row['fully_observed_survivors']) for _, row in covered), len(recurring))
            population['budgets'][str(budget)] = result
        populations[provenance] = population
    return {
        'format': 'specialization-fossil-v1', 'build_id': metadata[0]['build_id'],
        'recordings': metadata, 'trace_summaries': summaries,
        'baseline': baseline, 'populations': populations,
        'limits': [
            'Profile agreement does not validate native-code reuse or predict a speedup.',
            'Multiple-variant survival uses hindsight, not an implemented entry-time selector.',
            'Compilation durations include instrumentation and overlapping work; they are not latency savings.',
            'Ion code bytes exclude metadata, relocations, binding and dependency registration costs.',
            'Missing source and root selected CacheIR are exclusions; unseen sites and missing end events are censored.',
            'Root projections do not validate inlined targets, prototype identities, constants or optimizer guards.',
            'Baseline joins pair installation order within PID/address only when multiplicities match and process identity is unambiguous.',
            'Repeated benchmark inputs measure recurrence on those inputs, not arbitrary cross-site generalization.',
        ],
    }


def main():
    if '--directory' in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument('--directory', type=Path, required=True)
        args = parser.parse_args()
        report = analyze(args.directory)
    else:
        observation = json.load(sys.stdin)
        records = [json.loads(line) for line in observation['stdout'] if line.strip()]
        reports = [r for r in records if r.get('event') == 'specialization_experiment']
        if len(reports) != 1:
            raise ValueError('Expected exactly one completed specialization experiment')
        report = reports[0]['report']
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
