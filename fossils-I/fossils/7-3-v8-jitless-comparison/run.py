#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from dataclasses import replace
from browser import AOT_ONLY, NO_ION, NO_REGEX, raptor
from execution import Run, raptor_result, run
from settings import OCTANE_DIR, OCTANE_RUNNER, V8
from shell import octane

variant = sys.argv[1]
if variant.startswith('octane-v8-'):
    flags = {'octane-v8-default': (), 'octane-v8-jitless': ('--jitless',)}[variant]
    run(Run((V8 / 'd8/release/d8', *flags, OCTANE_RUNNER), cwd=OCTANE_DIR))
elif variant.startswith('octane-'):
    policy = {'octane-am': 'aot-corpus', 'octane-am-oracle': 'aot-corpus',
              'octane-baseline': 'default-no-ion', 'octane-default': 'default'}[variant]
    command = octane(policy)
    if variant == 'octane-baseline':
        command = replace(command, argv=(*command.argv[:-2], '--no-native-regexp',
                                         *command.argv[-2:]))
    run(command)
elif variant.startswith('speedometer-v8-'):
    flags = {'speedometer-v8-default': (),
             'speedometer-v8-jitless': ('--browsertime-arg', 'chrome.args=--js-flags=--jitless')}[variant]
    raptor_result(Run(
        ('./mach', 'raptor', '-t', 'speedometer3', '--app', 'chrome',
         '--browser-cycles', '1', '--page-cycles', '3',
         '--binary', V8 / 'run-chromium-nixos.sh',
         '--browsertime-chromedriver', V8 / 'run-chromedriver-nixos.sh',
         '--browsertime-arg', 'chrome.args=--headless=new', *flags),
    ))
else:
    environment, options = {
        'speedometer-am': ({**AOT_ONLY, **NO_REGEX}, NO_ION),
        'speedometer-am-oracle': ({**AOT_ONLY, **NO_REGEX}, NO_ION),
        'speedometer-baseline': (NO_REGEX, NO_ION),
        'speedometer-default': ({}, ()),
    }[variant]
    raptor_result(raptor('speedometer3', environment=environment, options=options))
