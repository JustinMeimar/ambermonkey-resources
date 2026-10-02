import re

from . import manifest

SCORE = re.compile(r'^Score \(version \d+\): ([0-9]+(?:\.[0-9]+)?)\s*$')
RESULT = re.compile(r'^([A-Za-z][A-Za-z0-9_\-]*): ([0-9]+(?:\.[0-9]+)?)\s*$')


def lines(observation):
    return [line for key in ('stdout', 'stderr')
            for line in (observation.get(key, '').splitlines()
                         if isinstance(observation.get(key), str)
                         else observation.get(key) or [])]


def parse_scores(lines, prefix='octane', *, reject_duplicates=True):
    workloads, score = {}, None
    for line in lines:
        match = SCORE.match(line)
        if match:
            score = float(match.group(1))
            continue
        match = RESULT.match(line)
        if match:
            name, value = match.groups()
            if reject_duplicates and name in workloads:
                manifest.fail(prefix, f'duplicate workload result {name!r}')
            workloads[name] = float(value)
    return workloads, score
