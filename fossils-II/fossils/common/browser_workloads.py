TESTS = {
    'speedometer3': ('speedometer3', 1),
    'jetstream3': ('jetstream3', 1),
    'tp6': ('browsertime-tp6', 2),
}
MANUAL_SECONDS = 180
PROFILE_PREFS = (
    'user_pref("browser.shell.checkDefaultBrowser", false);\n'
    'user_pref("browser.aboutwelcome.enabled", false);\n'
    'user_pref("browser.startup.homepage_override.mstone", "ignore");\n'
)


def raptor_command(launcher, browser, workload, environment=None):
    test, page_cycles = TESTS[workload]
    command = [*launcher, 'raptor', '-t', test, '--app', 'firefox',
               '--binary', str(browser), '--browser-cycles', '1',
               '--page-cycles', str(page_cycles)]
    for key, value in (environment or {}).items():
        command.extend(['--setenv', f'{key}={value}'])
    if workload == 'jetstream3':
        command.extend(['--test-url-params', 'tag=js&iterationCount=3&worstCaseCount=1'])
    return command
