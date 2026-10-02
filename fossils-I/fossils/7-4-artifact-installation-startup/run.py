#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from browser import AOT_ONLY, IC_ONLY, NO_ION, NO_REGEX, raptor
from execution import raptor_result

environment = {'default-no-ion': {}, 'aot-corpus-ic': IC_ONLY, 'aot-corpus': AOT_ONLY}
raptor_result(raptor(
    'jetstream3', page_cycles=1,
    environment={**environment[sys.argv[1]], **NO_REGEX},
    options=('--post-startup-delay', '1000', *NO_ION,
             '--setpref', 'javascript.options.wasm=false',
             '--test-url-params', 'tags=startup&iterationCount=2&worstCaseCount=1'),
))
