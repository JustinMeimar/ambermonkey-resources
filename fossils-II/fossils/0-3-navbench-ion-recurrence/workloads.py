"""Resolve Fossil variant names into NavBench interactive command sequences."""
import hashlib
from pathlib import Path
import sys
import tomllib
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'common'))
from navbench_routes import command_override, routes, workload as route_workload  # noqa: E402,F401

EXCLUDED_DOMAINS = ('youtube.com', 'youtu.be', 'reddit.com', 'x.com',
                    'twitter.com', 'linkedin.com')


def filter_commands(commands):
    """Drop excluded visits, including measurements, interactions and idle time."""
    blocks = [[]]
    for command in commands:
        if command[0] == 'measure.start':
            blocks.append([])
        blocks[-1].append(command)
    result = []
    excluded = False
    for block in blocks:
        for operation, argument in block:
            if operation == 'navigate' and argument != 'about:blank':
                host = urlsplit(argument).hostname or ''
                excluded = any(host == domain or host.endswith('.' + domain)
                               for domain in EXCLUDED_DOMAINS)
                break
        if not excluded:
            result.extend(block)
    return result


def variants():
    return ['navbench', *routes()]


def workload(variant, root):
    if variant != 'navbench':
        return route_workload(variant)
    manifest = root / 'testing/raptor/raptor/tests/nav-bench/browsertime-nav-bench.toml'
    source = manifest.read_bytes()
    commands = tomllib.loads(source.decode())['nav-bench']['test_cmds']
    return {'variant': variant, 'source': str(manifest),
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'test_cmds': filter_commands(commands)}
