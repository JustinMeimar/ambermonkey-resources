#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
import subprocess
from browser import AOT_ONLY, IC_ONLY, NO_REGEX
from execution import JIT_ENVIRONMENT, Run, run
from settings import MOZCONFIG_AOT

environment = {'default-no-ion': {}, 'aot-corpus-ic': IC_ONLY, 'aot-corpus': AOT_ONLY}
run(Run(
    ('./mach', 'talos-test', '-a', 'cpstartup'),
    environment={'MOZCONFIG': MOZCONFIG_AOT, 'MOZ_DISABLE_CONTENT_SANDBOX': '1',
                 'JS_AOT_TIMING': '1', 'JIT_OPTION_ion': 'false',
                 **NO_REGEX, **environment[sys.argv[1]]},
    unset=JIT_ENVIRONMENT,
), stderr=subprocess.STDOUT)
