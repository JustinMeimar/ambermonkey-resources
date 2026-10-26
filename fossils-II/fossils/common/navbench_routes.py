"""Live NavBench routes driven by Browsertime's interactive script."""
import hashlib
import json
from pathlib import Path
import shutil
import tomllib

CONFIG = Path(__file__).with_suffix('.toml')


def routes():
    return list(tomllib.loads(CONFIG.read_text())['routes'])


def workload(variant):
    source = CONFIG.read_bytes()
    config = tomllib.loads(source.decode())
    route = config['routes'][variant]['visits']
    commands = []
    if config['warmup_ms']:
        commands.append(['wait.byTime', str(config['warmup_ms'])])
    for repeat in range(1, config['passes'] + 1):
        for visit, page in enumerate(route, 1):
            commands.extend([
                ['measure.start', f'{page}-pass{repeat}-visit{visit:02d}-load'],
                ['navigate', config['pages'][page]],
                ['wait.byTime', str(config['dwell_ms'])],
                ['measure.stop', ''],
                ['navigate', 'about:blank'],
                ['wait.byTime', str(config['blank_ms'])],
            ])
    return {'variant': variant, 'source': str(CONFIG),
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'passes': config['passes'], 'route': route, 'test_cmds': commands}


def command_override(plan):
    commands = plan['test_cmds']
    if any(';;;' in str(arg) or ':::' in str(arg) for cmd in commands for arg in cmd):
        raise ValueError('Reserved Browsertime delimiter in workload')
    packed = ';;;'.join(':::'.join(map(str, cmd)) for cmd in commands)
    return ['--browsertime-arg', 'browsertime.commands=' + packed]


def browsertime_command(root, browser, plan, directory, environment):
    packed = command_override(plan)[1].split('=', 1)[1]
    command = ['./mach', 'browsertime',
               str(root / 'testing/raptor/browsertime/browsertime_interactive.js'),
               '-b', 'firefox', '--firefox.binaryPath', str(browser),
               '--iterations', '1', '--browsertime.page_cycles', '1',
               '--browsertime.post_startup_delay', '0',
               '--browsertime.commands', packed,
               '--firefox.profileTemplate', str(directory / 'profile'),
               '--firefox.noDefaultPrefs',
               '--firefox.disableBrowsertimeExtension', 'true',
               '--pageLoadStrategy', 'none', '--webdriverPageload', 'true',
               '--pageCompleteCheckStartWait', '5000',
               '--pageCompleteCheckPollTimeout', '1000',
               '--beforePageCompleteWaitTime', '2000',
               '--pageCompleteWaitTime', '5000',
               '--timeouts.pageLoad', '120000', '--timeouts.script', '600000',
               '--viewPort', '1280x1024', '--video', 'false',
               '--visualMetrics', 'false', '--skipHar',
               '--resultDir', str(directory / 'browsertime')]
    for key, value in environment.items():
        command.extend(['--firefox.env', f'{key}={value}'])
    return command


def prepare_profile(root, directory):
    profiles = root / 'testing/profiles'
    target = directory / 'profile'
    prefs = []
    for name in json.loads((profiles / 'profiles.json').read_text())['raptor']:
        source = profiles / name
        shutil.copytree(source, target, dirs_exist_ok=True)
        prefs.append((source / 'user.js').read_text())
    prefs.append('''
user_pref("fission.bfcacheInParent", false);
user_pref("browser.sessionhistory.max_total_viewers", 0);
user_pref("network.http.http3.enable", false);
user_pref("network.http.altsvc.enabled", false);
user_pref("network.dns.forceResolve", "");
''')
    (target / 'user.js').write_text('\n'.join(prefs))


def validate_visits(plan, directory):
    # The interactive driver catches command failures, so a successful harness
    # exit alone does not mean the requested route completed.
    if 'Exception found while running' in (directory / 'harness.log').read_text(errors='replace'):
        raise ValueError(f'Navigation command failed; see {directory / "harness.log"}')
    results = json.loads((directory / 'browsertime/browsertime.json').read_text())
    expected = [cmd[1] for cmd in plan['test_cmds'] if cmd[0] == 'measure.start']
    actual = [result['info'].get('alias') for result in results]
    if actual != expected or any(any(result.get('errors', [])) for result in results):
        raise ValueError(f'Incomplete or failed live route; see {directory / "browsertime"}')
