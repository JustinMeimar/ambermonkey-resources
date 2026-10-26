#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
import subprocess
import tempfile
import shutil
from browser import NO_ION
from execution import Run, run
from settings import BIN_RELEASE, BIN_AOT, MOZCONFIG_RELEASE, MOZCONFIG_AOT, SCRATCH

CLEAN = ('MOZ_HEADLESS', 'IONFLAGS', *(f'JIT_OPTION_{name}' for name in (
    'aotEnforce', 'aotOnly', 'aotRecordDir', 'baselineJit', 'disableJitBackend', 'ion', 'useAOTImage',
)))
fossil = Path(__file__).resolve().parent
binary, mozconfig, options = {
    'interp-only': (BIN_RELEASE, MOZCONFIG_RELEASE, ('--setenv', 'JIT_OPTION_disableJitBackend=true')),
    'default': (BIN_RELEASE, MOZCONFIG_RELEASE, ()),
    'default-no-ion': (BIN_RELEASE, MOZCONFIG_RELEASE, NO_ION),
    'aot-corpus': (BIN_AOT, MOZCONFIG_AOT, ('--setenv', 'JIT_OPTION_useAOTImage=true',
                                         '--setenv', 'JIT_OPTION_aotOnly=true', *NO_ION)),
}[sys.argv[1]]
directory = tempfile.mkdtemp(prefix='amber-7-6.', dir=SCRATCH)
with (Path(directory) / 'sidecar.log').open('w') as log:
    sidecar = subprocess.Popen(
        ('python3', str(fossil / 'scripts/smaps_sidecar.py'), '--dir', directory,
         '--parent-exe', str(binary), '--poll-ms', '50', '--interval-ms', '2000'),
        stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        run(Run(
            ('./mach', 'raptor', '-t', 'speedometer3', '--app', 'firefox',
             '--browser-cycles', '1', '--page-cycles', '3', '--binary', binary,
             '--setenv', 'MOZ_HEADLESS=1', *options),
            environment={'MOZCONFIG': mozconfig, 'MOZ_DISABLE_CONTENT_SANDBOX': '1'},
            unset=CLEAN,
        ), stdout=sys.stderr, check=False)
    finally:
        sidecar.terminate()
        sidecar.wait()
run(Run(('python3', fossil / 'scripts/emit_summary.py', directory), cwd=fossil))
shutil.rmtree(directory)
