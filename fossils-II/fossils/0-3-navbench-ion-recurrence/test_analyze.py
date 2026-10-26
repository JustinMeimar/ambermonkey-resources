import unittest

from analyze import summarize


def compilation(script, template='a', function='f', pid=1, **fields):
    return dict(event='compile', schema=2, pid=pid, script=script,
                function=function, template=template, t_us=0,
                backend_us=10, self_hosted=False, system=False, **fields)


class RecurrenceTests(unittest.TestCase):
    def test_recompilation_needs_another_instance(self):
        result = summarize([compilation('a'), compilation('a')])
        self.assertEqual(result['function_recurrence'], 0)
        self.assertEqual(result['template_recurrence'], 0)
        self.assertEqual(result['template_recurrence_count'], 0)

    def test_cross_process_match_and_return_to_first_instance(self):
        result = summarize([compilation('a'), compilation('a', pid=2),
                            compilation('a')])
        self.assertEqual(result['function_recurrence'], 2 / 3)
        self.assertEqual(result['template_recurrence'], 2 / 3)
        self.assertEqual(result['function_recurrence_count'], 2 / 3)
        self.assertEqual(result['template_recurrence_count'], 2 / 3)

    def test_weighting_and_function_partition(self):
        events = [compilation('a'), compilation('b', template='b'),
                  compilation('c', function='g'), compilation('d')]
        events[-1]['backend_us'] = 70
        result = summarize(events)
        self.assertEqual(result['backend_ms'], 0.1)
        self.assertEqual(result['function_recurrence'], 0.8)
        self.assertEqual(result['template_recurrence'], 0.7)
        self.assertEqual(result['function_recurrence_count'], 0.5)
        self.assertEqual(result['template_recurrence_count'], 0.25)

    def test_chrome_and_invalidations_do_not_seed_cache(self):
        chrome = compilation('a')
        chrome['system'] = True
        result = summarize([chrome, {'event': 'invalidate'}, compilation('b')])
        self.assertEqual(result['compilations'], 1)
        self.assertEqual(result['template_recurrence'], 0)
        self.assertEqual(result['template_recurrence_count'], 0)

    def test_unavailable_or_mixed_schema_rejected(self):
        with self.assertRaises(ValueError):
            summarize([compilation('a', template='0' * 16)])
        legacy = compilation('a')
        del legacy['schema']
        with self.assertRaises(ValueError):
            summarize([legacy, compilation('b')])
        self.assertEqual(summarize([legacy])['template_recurrence'], 0)


if __name__ == '__main__':
    unittest.main()
