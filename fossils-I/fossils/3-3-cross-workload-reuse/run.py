#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
import tempfile
import shutil
from execution import Run, run
from settings import BIN_RELEASE, MOZCONFIG_RELEASE, SCRATCH

fossil = Path(__file__).resolve().parent
directory = tempfile.mkdtemp(prefix='amber-3-3.', dir=SCRATCH)
run(Run(
    ('./mach', 'raptor', '-t', sys.argv[1], '--binary', BIN_RELEASE,
     '--setenv', 'JS_INSTR=lifecycle,ic,demand,baseline',
     '--setenv', f'JS_INSTR_DIR={directory}', '--setenv', 'JS_INSTR_MODE=demand',
     '--setenv', f'JS_INSTR_RUN_ID={Path(directory).name}',
     '--setenv', 'MOZ_DISABLE_CONTENT_SANDBOX=1', '--setenv', 'MOZ_HEADLESS=1',
     '--cold', '--page-cycles', '1', '--browser-cycles', '3',
     '--post-startup-delay', '1000'),
    environment={'MOZCONFIG': MOZCONFIG_RELEASE},
), stdout=sys.stderr)
run(Run(('python3', fossil / 'scripts/emit_ranks.py', directory), cwd=fossil))
shutil.rmtree(directory)
