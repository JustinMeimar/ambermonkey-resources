#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from browser import NO_ION, raptor
from execution import raptor_result

options = {
    'speedometer3-default': (),
    'speedometer3-aot-only': (
        '--setenv', 'JIT_OPTION_useAOTImage=true',
        '--setenv', 'JIT_OPTION_aotOnly=true',
        '--setenv', 'JIT_OPTION_nativeRegExp=false', *NO_ION),
}
raptor_result(raptor('speedometer3', options=options[sys.argv[1]]))
