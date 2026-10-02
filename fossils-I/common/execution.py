from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys

from settings import FIREFOX

JIT_ENVIRONMENT = (
    'MOZ_HEADLESS', 'IONFLAGS',
    *(f'JIT_OPTION_{name}' for name in (
        'aotEnforce', 'aotOnly', 'aotRecordDir', 'aotSelfHostedBaselineOnly',
        'aotSkipBaselineFn', 'baselineInterpreterWarmUpThreshold', 'baselineJit',
        'disableCacheIR', 'disableJitBackend', 'ion', 'useAOTBaseline',
        'useAOTIC', 'useAOTImage', 'nativeRegExp',
    )),
)


@dataclass(frozen=True)
class Run:
    argv: tuple
    cwd: Path = FIREFOX
    environment: dict = field(default_factory=dict)
    unset: tuple = ()


def run(command, *, stdout=None, stderr=None, check=True):
    argv = list(map(str, command.argv))
    environment = {k: v for k, v in os.environ.items() if k not in command.unset}
    environment.update({k: str(v) for k, v in command.environment.items()})
    print('AMBER_EXECUTION=' + json.dumps({
        'argv': argv,
        'cwd': str(command.cwd),
        'environment': {k: str(v) for k, v in command.environment.items()},
        'unset': command.unset,
    }), file=sys.stderr, flush=True)
    result = subprocess.run(argv, cwd=command.cwd, env=environment,
                            stdout=stdout, stderr=stderr)
    if check and result.returncode:
        raise SystemExit(result.returncode if result.returncode > 0 else 128 - result.returncode)
    return result


def raptor_result(command):
    run(command, stdout=sys.stderr)
    sys.stdout.write((FIREFOX / 'testing/mozharness/build/raptor.json').read_text())
