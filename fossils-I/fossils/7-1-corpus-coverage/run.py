#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
import tempfile
import shutil
from execution import Run, run
from settings import BIN_AOT, JSSHELL_AOT, MOZCONFIG_AOT, OCTANE_DIR, OCTANE_RUNNER, SCRATCH

fossil = Path(__file__).resolve().parent
variant = sys.argv[1]
directory = tempfile.mkdtemp(prefix='amber-7-1.', dir=SCRATCH)
if variant == 'octane2':
    run(Run((JSSHELL_AOT, '--wasm-compiler=none', '--aot', '-f', OCTANE_RUNNER),
            cwd=OCTANE_DIR, environment={'JS_AOT_COVERAGE_OUT': f'{directory}/cov'}),
        stdout=sys.stderr)
else:
    workloads = ('reddit', 'tumblr', 'twitch', 'twitter', 'wikia', 'wikipedia',
                 'yahoo-mail', 'youtube') if variant == 'tp6_test' else (variant,)
    for workload in workloads:
        run(Run(
            ('./mach', 'raptor', '--binary', BIN_AOT,
             '--page-cycles', '1', '--browser-cycles', '1',
             '--setenv', 'JIT_OPTION_useAOTImage=true',
             '--setenv', f'JS_AOT_COVERAGE_OUT={directory}/cov',
             '--setenv', 'MOZ_DISABLE_CONTENT_SANDBOX=1', '--setenv', 'MOZ_HEADLESS=1',
             '--post-startup-delay', '1000', '-t', workload),
            environment={'MOZCONFIG': MOZCONFIG_AOT},
        ), stdout=sys.stderr)
run(Run(('python3', fossil / 'scripts/reduce_coverage.py', directory), cwd=fossil))
shutil.rmtree(directory)
