#!/usr/bin/env python3
"""Launch Firefox directly; emit Ion recurrence events after the user closes it."""
import argparse
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
import time

from analyze import read_events, summarize
from workloads import variants, workload

ROOT = Path(os.environ.get('FIREFOX_ROOT', '/home/justin/spidermonkey/firefox'))
BROWSER = ROOT / 'build-browser-release/dist/bin/firefox'


def browser_command(plan, directory):
    return [str(BROWSER), '--no-remote', '--profile', str(directory / 'profile'),
            plan['route'][0]['url']]


def browser_environment(directory):
    env = dict(os.environ)
    # Do not inherit a previous harness's automation or trace configuration.
    for key in ('MOZ_AUTOMATION', 'MOZ_HEADLESS', 'MOZ_MARIONETTE',
                'MOZ_MARIONETTE_PORT', 'MOZ_REMOTE_SETTINGS_DEVTOOLS',
                'MOZ_DISABLE_NONLOCAL_CONNECTIONS', 'MOZ_LOG', 'MOZ_LOG_FILE',
                'IONFLAGS', 'JS_SPECIALIZATION_HINTS'):
        env.pop(key, None)
    env.update(MOZ_LOG='ionRecurrence:3,sync,append',
               MOZ_LOG_FILE=str(directory / 'trace%PID'))
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=variants())
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the route and command without opening Firefox')
    args = parser.parse_args()
    plan = workload(args.variant)
    directory = ROOT / 'artifacts/ion-recurrence-direct' / f'{time.time_ns()}-{args.variant}'
    command = browser_command(plan, directory)
    if args.dry_run:
        print(json.dumps({'workload': plan, 'command': command}, indent=2))
        return
    with (BROWSER.parent / 'libxul.so').open('rb') as library:
        with mmap.mmap(library.fileno(), 0, access=mmap.ACCESS_READ) as contents:
            if contents.find(b'IONREC {"schema":2,') < 0:
                sys.exit('libxul.so needs schema 2 Ion recurrence logging; rebuild first.')
    (directory / 'profile').mkdir(parents=True)
    # Normal Firefox defaults, with only first-run prompts suppressed.
    (directory / 'profile/user.js').write_text(
        'user_pref("browser.shell.checkDefaultBrowser", false);\n'
        'user_pref("browser.aboutwelcome.enabled", false);\n'
        'user_pref("browser.startup.homepage_override.mstone", "ignore");\n')
    (directory / 'workload.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(f'Opening {args.variant}. Browse manually; close this Firefox to finish.',
          file=sys.stderr, flush=True)
    print(f"Suggested route, repeated {plan['passes']} times:", file=sys.stderr)
    for visit, page in enumerate(plan['route'], 1):
        print(f"  {visit}. {page['page']}: {page['url']}", file=sys.stderr)
    print(f'Logs: {directory}', file=sys.stderr, flush=True)
    with (directory / 'browser.log').open('w') as log:
        status = subprocess.run(command, cwd=ROOT, env=browser_environment(directory),
                                stdout=log, stderr=subprocess.STDOUT).returncode
    if status:
        sys.exit(f'Firefox exited with status {status}; see {directory / "browser.log"}')
    events = read_events(directory)
    if any(event.get('schema') != 2 for event in events):
        sys.exit('Unexpected Ion recurrence schema; rebuild the release browser.')
    summarize(events)
    for event in events:
        print('IONREC ' + json.dumps(event, separators=(',', ':')))
    print(json.dumps({'directory': str(directory), 'exit_code': status,
                      'browser': str(BROWSER), 'events': len(events),
                      'compilations': sum(e['event'] == 'compile' for e in events),
                      'workload': plan}))


if __name__ == '__main__':
    main()
