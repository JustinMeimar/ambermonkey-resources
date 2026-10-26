"""Approved routes used as references for manual Firefox sessions."""
import hashlib
from pathlib import Path
import tomllib

CONFIG = Path(__file__).with_suffix('.toml')


def variants():
    return list(tomllib.loads(CONFIG.read_text())['routes'])


def workload(variant):
    source = CONFIG.read_bytes()
    config = tomllib.loads(source.decode())
    route = config['routes'][variant]['visits']
    return {'variant': variant, 'mode': 'manual-live',
            'source': str(CONFIG),
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'passes': config['passes'],
            'route': [{'page': page, 'url': config['pages'][page]} for page in route],
            'route_enforced': False}
