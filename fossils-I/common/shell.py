from execution import JIT_ENVIRONMENT, Run
from settings import JSSHELL_AOT, OCTANE_DIR, OCTANE_RUNNER

AOT_FLAGS = ('--aot', '--aot-only', '--no-native-regexp', '--no-ion')


def octane(variant):
    flags = {
        'interp-only': ('--no-jit-backend',),
        'blinterp-only': ('--blinterp-eager', '--no-baseline',
                         '--cache-ir-stubs=off', '--no-native-regexp', '--no-ion'),
        'aot-corpus-ic': AOT_FLAGS,
        'aot-corpus': AOT_FLAGS,
        'default-no-ion': ('--no-ion',),
        'default': (),
    }[variant]
    return Run(
        (JSSHELL_AOT, '--wasm-compiler=none', *flags, '-f', OCTANE_RUNNER),
        cwd=OCTANE_DIR,
        environment={'JIT_OPTION_aotSkipBaselineFn': 'true'}
                    if variant == 'aot-corpus-ic' else {},
        unset=JIT_ENVIRONMENT,
    )
