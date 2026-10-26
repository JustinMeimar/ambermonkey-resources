#!/usr/bin/env python3
"""Run Talos against a packaged browser without a configured Firefox build."""
import os
from pathlib import Path
import sys

from mozbuild.base import MozbuildObject

firefox = Path(os.environ['AMBERMONKEY_FIREFOX'])
sys.path.insert(0, str(firefox / 'testing/mozharness'))
from mozharness.mozilla.testing.talos import Talos

objdir = Path(MozbuildObject.from_environment(cwd=str(firefox)).topobjdir)
(objdir / 'testing').mkdir(parents=True, exist_ok=True)
setup_only = '--setup-only' in sys.argv
arguments = [arg for arg in sys.argv[1:] if arg != '--setup-only']
config = {
    'run_local': True,
    'talos_json': str(firefox / 'testing/talos/talos.json'),
    'binary_path': os.environ['AMBERMONKEY_BIN_AOT'],
    'repo_path': str(firefox),
    'obj_path': str(objdir),
    'base_work_dir': str(firefox / 'testing/mozharness'),
    'virtualenv_path': str(objdir / 'testing/talos-venv'),
    'mozbuild_path': os.environ.get('MOZBUILD_STATE_PATH', '/root/.mozbuild'),
    'exes': {'python': sys.executable},
    'talos_extra_options': ['--develop', *(arguments or ['-a', 'cpstartup'])],
    'log_name': 'talos',
    'pip_index': True,
}
harness = Talos(config=config, option_args=[],
                default_actions=['populate-webroot', 'create-virtualenv'] +
                ([] if setup_only else ['run-tests']))
raise SystemExit(harness.run())
