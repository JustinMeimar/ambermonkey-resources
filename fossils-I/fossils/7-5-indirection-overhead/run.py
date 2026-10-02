#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from execution import Run, run
from settings import (JSSHELL_RIT, JSSHELL_NATIVE_LINKER,
                      JSSHELL_NATIVE_LINKER_VALUE_MIRROR)

shell, flags = {
    'baseline-jit': (JSSHELL_NATIVE_LINKER_VALUE_MIRROR, ('--blinterp-eager', '--no-ion')),
    'am-rit': (JSSHELL_RIT, ('--blinterp-eager', '--aot', '--aot-enforce', '--no-ion')),
    'am-rit-nl': (JSSHELL_NATIVE_LINKER, ('--blinterp-eager', '--aot', '--aot-enforce', '--no-ion')),
    'am-rit-nl-vm': (JSSHELL_NATIVE_LINKER_VALUE_MIRROR, ('--blinterp-eager', '--aot', '--aot-enforce', '--no-ion')),
}[sys.argv[1]]
fossil = Path(__file__).resolve().parent
run(Run(('bash', fossil / 'scripts/run_all_microbenches.sh', shell, *flags), cwd=fossil))
