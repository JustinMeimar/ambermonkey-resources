from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
AMBERMONKEY = PROJECT.parent
FIREFOX = AMBERMONKEY.parent / 'firefox'
BIN_RELEASE = FIREFOX / 'build-browser-release/dist/bin/firefox'
BIN_AOT = FIREFOX / 'build-browser-release-aot/dist/bin/firefox'
JSSHELL_AOT = FIREFOX / 'build-shell-release-aot/dist/bin/js'
JSSHELL_RIT = FIREFOX / 'js-perf-eval-rit'
JSSHELL_NATIVE_LINKER = FIREFOX / 'js-perf-eval-native-linker'
JSSHELL_NATIVE_LINKER_VALUE_MIRROR = FIREFOX / 'js-perf-eval-native-linker-value-mirror'
MOZCONFIG_RELEASE = AMBERMONKEY / 'mozconfigs/browser-release.mozconfig'
MOZCONFIG_AOT = AMBERMONKEY / 'mozconfigs/browser-release-aot.mozconfig'
V8 = AMBERMONKEY / 'v8-project'
SCRATCH = Path('/tmp')
CORPUS = SCRATCH / 'amber-aot-corpus'
SELFHOSTED = SCRATCH / 'amber-aot-selfhosted'
SELECTED_CORPUS = SCRATCH / 'amber-aot-corpus-selected'
OCTANE_DIR = FIREFOX / 'js/src/octane'
OCTANE_RUNNER = PROJECT / 'common/run-octane.js'
