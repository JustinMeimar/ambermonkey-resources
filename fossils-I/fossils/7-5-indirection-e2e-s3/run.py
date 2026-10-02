#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from browser import AOT_ONLY, NO_ION, NO_REGEX, raptor
from execution import raptor_result

environment = {'default-no-ion': NO_REGEX, 'aot-corpus': {**AOT_ONLY, **NO_REGEX}}
raptor_result(raptor('speedometer3', environment=environment[sys.argv[1]], options=NO_ION))
