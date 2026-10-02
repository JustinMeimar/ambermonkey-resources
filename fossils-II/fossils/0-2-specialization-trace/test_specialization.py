#!/usr/bin/env python3
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest

import analyze
import specialization_cache as sc


def frames(event):
    data = json.dumps(event).encode()
    pieces = [data[i:i + 512] for i in range(0, len(data), 512)]
    return [f'logger SPCACHE2\t{event["pid"]}\t{event["process_start_us"]}\t'
            f'{event["sequence"]}\t{i}\t{len(pieces)}\t{piece.hex()}\n'
            for i, piece in enumerate(pieces)]


class TraceTests(unittest.TestCase):
    def decode(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.log'
            path.write_text(''.join(lines))
            return list(sc.extract([path], 'test'))

    def test_interleaved_large_records(self):
        events = [dict(version=2, event='script', pid=pid, process_start_us=9,
                       sequence=2, filename='é' * 3000) for pid in (10, 11)]
        lines = list(itertools.chain.from_iterable(zip(*map(frames, events))))
        self.assertEqual(self.decode(lines), [dict(e, run='test') for e in events])

    def test_incomplete_duplicate_and_corrupt_frames_fail(self):
        event = dict(version=2, pid=10, process_start_us=9, sequence=2, data='x' * 2000)
        lines = frames(event)
        for broken in (lines[:-1], lines + lines, [lines[0].replace('\t0\t', '\t99\t', 1)],
                       [lines[0].rstrip() + 'nothex\n'], ['SPCACHE\t{}\n'], []):
            with self.subTest(broken=broken[:1]), self.assertRaises(ValueError):
                self.decode(broken)

    def test_diagnostic_has_filename_and_line(self):
        with self.assertRaisesRegex(ValueError, 'trace.log:1:'):
            self.decode(['SPCACHE2\tbroken\n'])

    def recording(self, inline_ir='bb', pointer='1234', scalar='01', source=8,
                  success=True, dependencies=None, directory=None, pid=10, run='test'):
        events = []
        def emit(kind, **fields):
            events.append(dict(version=2, pid=pid, process_start_us=9,
                               sequence=len(events) + 1, build_id='test', run=run, event=kind, **fields))
        for owner, key in ((1, 'root'), (2, 'inline')):
            emit('script', ic_script=owner, key=key, source_encoding=source,
                 self_hosted=False, system_realm=False)
        emit('ion_request', compilation=3, ic_script=1)
        for owner, ir in ((1, 'aa'), (2, inline_ir)):
            emit('profile', compilation=3, ic_script=owner)
            emit('selected', compilation=3, ic_script=owner, offset=4,
                 stubs=[dict(kind=0, ir=ir, type_data=0, fields=[
                     dict(type='RawInt32', scalar=True, bits=scalar),
                     dict(type='WeakObject', scalar=False, bits=pointer)])])
        emit('dependencies', compilation=3, types=dependencies or [])
        emit('ion_compile', compilation=3, phase='backend', duration_us=42)
        emit('ion_link', compilation=3, ic_script=1, success=success, code_bytes=100, metadata_bytes=20)
        if directory is not None:
            (directory / 'specialization.jsonl').write_text('\n'.join(map(json.dumps, events)))
            return
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'specialization.jsonl').write_text('\n'.join(map(json.dumps, events)))
            return sc.read_recording(directory)['populations']['guest']

    def test_three_recording_report_and_overlap_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for pid, label in enumerate(analyze.LABELS, 10):
                directory = root / label
                directory.mkdir()
                self.recording(directory=directory, pid=pid, run=f'speedometer3-{label}')
                (directory / 'run.json').write_text(json.dumps(dict(
                    build_id='test', workload='speedometer3', environment={})))
                (directory / 'summary.json').write_text(json.dumps(dict(exit_code=0, trace_version=2)))
            report = analyze.analyze(root)
            guest = report['populations']['guest']
            self.assertEqual(guest['evaluation_links_at_recurring_keys'], analyze.fraction(1, 1))
            self.assertEqual(guest['projection_recurrence']['snapshot']['1']['matching_evaluation_links'],
                             analyze.fraction(1, 1))
            self.recording(directory=root / 'evaluation', pid=10, run='speedometer3-evaluation')
            with self.assertRaisesRegex(ValueError, 'same process'):
                analyze.analyze(root)

    def test_inline_drift_and_opaque_pointers(self):
        original = self.recording()['linked'][0]
        moved = self.recording(pointer='5678')['linked'][0]
        inline = self.recording(inline_ir='cc')['linked'][0]
        scalar = self.recording(scalar='02')['linked'][0]
        deps = self.recording(dependencies=[7])['linked'][0]
        self.assertEqual(original['snapshot'], moved['snapshot'])
        self.assertEqual(original['root'], inline['root'])
        self.assertNotEqual(original['snapshot'], inline['snapshot'])
        self.assertNotEqual(original['root'], scalar['root'])
        self.assertNotEqual(original['snapshot'], deps['snapshot'])
        self.assertEqual(original['opaque_fields'], {'WeakObject': 2})

    def test_failures_and_missing_source_are_not_matches(self):
        failed = self.recording(success=False)
        self.assertEqual((failed['requests'], failed['backend_us'], failed['linked']), (1, 42, []))
        missing = self.recording(source=0)
        self.assertEqual(missing['missing_source_links'], 1)
        self.assertIsNone(missing['linked'][0]['key'])
        self.assertIsNone(missing['linked'][0]['snapshot'])

    def test_selection_uses_training_and_explicit_denominators(self):
        a = self.recording()['linked'][0]
        b = self.recording(scalar='02')['linked'][0]
        excluded = copy.deepcopy(a)
        excluded['root'] = None
        result = analyze.recurrence([[a, b, b, b], [a]], [a, b, excluded], 'root', 1)
        self.assertEqual(result['matching_evaluation_links'], analyze.fraction(1, 2))
        self.assertEqual(result['variants_seen_in_both_training_runs'], 1)
        self.assertEqual(result['sum_variant_median_code_bytes'], 100)
        result = analyze.recurrence([[a, b], [a]], [a, b], 'root', 2)
        self.assertEqual(result['matching_evaluation_links'], analyze.fraction(2, 2))
        self.assertIsNone(analyze.recurrence([[], []], [], 'root', 1)['matching_evaluation_links']['percent'])


if __name__ == '__main__':
    unittest.main()
