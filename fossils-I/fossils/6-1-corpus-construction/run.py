#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
import json
import shutil
import subprocess
from execution import Run, run
from settings import BIN_AOT, CORPUS, JSSHELL_AOT, MOZCONFIG_AOT, SELFHOSTED

site = sys.argv[1]
directory = SELFHOSTED if site == 'self-hosted' else CORPUS / site
if directory.exists():
    shutil.rmtree(directory)
if site == 'self-hosted':
    command = Run((JSSHELL_AOT, '--spectre-mitigations=on',
                   f'--aot-record={directory}', '--aot-record-self-hosted', '-e', 'quit(0);'))
else:
    directory.mkdir(parents=True)
    command = Run(
        ('./mach', 'raptor', '-t', site, '--binary', BIN_AOT,
         '--setenv', f'JIT_OPTION_aotRecordDir={directory}',
         '--setenv', 'MOZ_DISABLE_CONTENT_SANDBOX=1', '--setenv', 'MOZ_HEADLESS=1',
         '--page-cycles', '1', '--browser-cycles', '1', '--post-startup-delay', '1000'),
        environment={'MOZCONFIG': MOZCONFIG_AOT},
    )
run(command, stdout=sys.stderr)
names = [entry.name for entry in directory.iterdir()]
size = subprocess.check_output(('du', '-sb', str(directory)), text=True).split()[0]
print(json.dumps({'site': site, 'blfun': sum(n.startswith('blfun-') for n in names),
                  'ic': sum(n.startswith('ic-') for n in names), 'bytes': int(size)}))
