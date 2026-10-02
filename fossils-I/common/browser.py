from execution import JIT_ENVIRONMENT, Run
from settings import BIN_AOT, MOZCONFIG_AOT

NO_ION = ('--setpref', 'javascript.options.ion=false')
NO_REGEX = {'JIT_OPTION_nativeRegExp': 'false'}
AOT_ONLY = {'JIT_OPTION_useAOTImage': 'true', 'JIT_OPTION_aotOnly': 'true'}
IC_ONLY = {'JIT_OPTION_useAOTIC': 'true', 'JIT_OPTION_aotOnly': 'true'}


def raptor(workload, *, binary=BIN_AOT, mozconfig=MOZCONFIG_AOT,
           page_cycles=3, browser_cycles=1, environment=None, options=(),
           clean=JIT_ENVIRONMENT, headless=True):
    return Run(
        ('./mach', 'raptor', '-t', workload, '--app', 'firefox',
         '--browser-cycles', str(browser_cycles), '--page-cycles', str(page_cycles),
         '--binary', binary,
         *(('--setenv', 'MOZ_HEADLESS=1') if headless else ()), *options),
        environment={'MOZCONFIG': mozconfig, 'MOZ_DISABLE_CONTENT_SANDBOX': '1',
                     **(environment or {})},
        unset=clean,
    )


def speedometer(variant):
    environment, options = {
        'interp-only': ({'JIT_OPTION_disableJitBackend': 'true'}, ()),
        'blinterp-only': ({'JIT_OPTION_baselineJit': 'false',
                          'JIT_OPTION_disableCacheIR': 'true',
                          'JIT_OPTION_baselineInterpreterWarmUpThreshold': '0',
                          **NO_REGEX}, NO_ION),
        'aot-corpus-ic': ({**AOT_ONLY, **NO_REGEX,
                           'JIT_OPTION_aotSkipBaselineFn': 'true'}, NO_ION),
        'aot-corpus': ({**AOT_ONLY, **NO_REGEX}, NO_ION),
        'default-no-ion': ({}, NO_ION),
        'default': ({}, ()),
    }[variant]
    return raptor('speedometer3', environment=environment, options=options)
