import os
import sys

from loguru import logger

from pytest_cleanup.recorder import save_example_scripts


def call_user_function(mod, fn: str):
    try:
        getattr(mod, fn)()
    except Exception as e:
        logger.error(e)
        logger.error(
            f'Error calling function {fn}. Does it exist in {mod} and is it a no-arg function? Otherwise, set one with PYTESTCLEANUP_FUNCTION.'
        )
        sys.exit(1)


def load_user_function(module_path):
    try:
        # must load module early so that Recorder can find it and patch it
        logger.debug('loading user module')
        mod = __import__(module_path, globals(), locals(), [], 0)
        return mod
    except Exception as e:
        logger.error(e)
        logger.error(f'Error finding module "{module_path}". Is this a real module name?')
        sys.exit(1)


def get_module_path(input_path):
    suffix = '.py'
    if input_path.endswith(suffix):
        input_path = input_path[: -len(suffix)]
    if input_path.startswith(os.getcwd()):
        module_file_path = input_path[len(os.getcwd()) + 1 :]
    else:
        module_file_path = input_path
    return module_file_path.replace(os.sep, '.')


def main():
    if len(sys.argv) < 2:
        save_example_scripts()
        return
    module_path = get_module_path(sys.argv[-1])
    module = load_user_function(module_path)

    from pytest_cleanup import Recorder, user_function

    with Recorder():
        call_user_function(module, user_function)


if __name__ == '__main__':
    main()
