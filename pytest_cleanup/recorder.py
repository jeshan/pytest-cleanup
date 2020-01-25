import functools
import inspect
import os
import sys
from fnmatch import fnmatch
from os.path import abspath
from threading import Thread
from typing import List, Dict

from loguru import logger

from pytest_cleanup.common import (
    get_test_data_filename,
    get_name,
    get_class_that_defined_method,
    mergeFunctionMetadata,
    log_level,
    is_async_fn,
    is_regular_function,
    try_dump_dill,
    pytestcleanup_decorated_with_record_test_data,
)
from pytest_cleanup.constants import test_data_directory, filename_count_limit, test_filename, test_directory

user_function = os.environ.get('PYTESTCLEANUP_FUNCTION', 'main')
invocation_limit_per_function = int(os.environ.get('PYTESTCLEANUP_TEST_CASE_COUNT_PER_FUNCTION', '5'))
serialisation_depth = int(os.environ.get('PYTESTCLEANUP_SERIALISATION_DEPTH', '500'))
filesize_limit = int(os.environ.get('PYTESTCLEANUP_FILESIZE_LIMIT_MB', '5')) * 1024 * 1024
allow_all_modules = 'PYTESTCLEANUP_ALLOW_ALL_MODULES' in os.environ
include_modules = os.environ.get('PYTESTCLEANUP_INCLUDE_MODULES', '').split(',')
exclude_modules = os.environ.get('PYTESTCLEANUP_EXCLUDE_MODULES', '').split(',')


def fn_description(f):
    return f'{f.__module__}.{f.__qualname__}'


def log_call(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        logger.debug(f'Entering {f}')
        return_value = f(*args, **kwargs)
        logger.debug(f'Exiting {f}')

        return return_value

    return wrapper


def log_error(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f'Error in {f} with {args[:2]}: {e}, skipping test cases for function.')

    return wrapper


def group_by_function(invocations: List) -> Dict[object, List]:
    result = {}
    for invocation in invocations:
        f = invocation['f']
        if f not in result:
            result[f] = []
        if len(result[f]) >= invocation_limit_per_function:
            continue
        if invocation in result[f]:
            continue
        result[f].append(invocation)
    return result


def is_site_package(module):
    return 'site-packages' in (get_dict(module).get('__file__') or {})


def exclude_importers(module):
    loader = get_dict(module).get('__loader__')
    loader_type = type(loader)
    if hasattr(loader_type, '__name__'):
        name = loader_type.__name__
    elif hasattr(loader, 'name'):
        name = loader.name
    if loader:
        qualified_name = loader_type.__module__ + '.' + name
    else:
        qualified_name = ''
    return qualified_name.endswith('._SixMetaPathImporter')


def is_system_package(module):
    from importlib._bootstrap import BuiltinImporter, FrozenImporter

    dict__ = get_dict(module)
    loader = dict__.get('__loader__')
    name__ = get_name(module)
    return (
        loader in [BuiltinImporter, FrozenImporter]
        or (
            hasattr(module, '__file__')
            and (module.__file__ is not None)
            and f"python{sys.version_info.major}.{sys.version_info.minor}/{(module.__package__ or '').replace('.', '/')}"
            in module.__file__
        )
        or name__.startswith('typing.')
    )


def get_dict(module):
    if hasattr(module, '__dict__'):
        return module.__dict__
    return {}


def get_module(name):
    return sys.modules.get(name)


def get_loaded_modules():
    import sys

    all_modules = []
    for name, module in sys.modules.items():
        all_modules.append((name, module))
    return all_modules


def singleton(cls):
    obj = cls()
    # Always return the same object
    cls.__new__ = staticmethod(lambda cls: obj)
    # Disable __init__
    try:
        del cls.__init__
    except AttributeError:
        pass
    return cls


def save_example_scripts():
    logger.debug(f'Saving example scripts under {test_directory}')
    with open(f'{test_directory}/{test_filename}', 'w') as f:
        f.write(
            f"""import pytest

from pytest_cleanup.common import is_function, assert_return_values


def test_pytest_cleanup_sync_test_cases(fn, args, kwargs, expected):
    ""\"See {test_data_directory} directory for test cases\"""
    actual = fn(*args, **kwargs)
    assert_return_values(actual, expected)


@pytest.mark.asyncio
async def test_pytest_cleanup_async_test_cases(fn, args, kwargs, expected):
    ""\"See {test_data_directory} directory for test cases.
    support for asyncio in pytest may be enabled by installing pytest-asyncio \"""
    actual = await fn(*args, **kwargs)
    assert_return_values(actual, expected)
"""
        )

    with open(f'{test_directory}/conftest-pytest-cleanup-runtime.py', 'w') as f:
        f.write(
            f"""def pytest_generate_tests(metafunc):
    from pytest_cleanup import parametrize_stg_tests

    parametrize_stg_tests(metafunc)


"""
        )

    with open(f'{test_directory}/conftest-pytest-cleanup-record.py', 'w') as f:
        f.write(
            f"""from pytest_cleanup import Recorder


def pytest_runtestloop(session):
    Recorder().enter()


def pytest_sessionfinish(session, exitstatus):
    Recorder().exit()


def pytest_sessionstart(session):
    Recorder().enter()


"""
        )


def print_invocation_group_summary(group):
    for fn, invocations in group.items():
        logger.debug(f'{fn.__module__}.{fn.__name__} got {len(invocations)} invocations')


def get_file(module):
    return module.__file__ if hasattr(module, '__file__') and module.__file__ else ''


def is_test_class(clazz):
    import unittest

    return issubclass(clazz, unittest.TestCase)


def are_cases_equal(first, second):
    return (
        first['args'] == second['args']
        and first['kwargs'] == second['kwargs']
        and first['return_value'] == second['return_value']
    )


def remove_duplicate_cases(cases):
    result = [cases[0]] if cases else []
    for case in cases:
        for item in result:
            if are_cases_equal(item, case):
                logger.trace('Duplicate case found; skipping adding it to the list')
            else:
                result.append(case)
                break
    return result


@singleton
class Recorder:
    def __init__(self):
        logger.info('creating instance of recorder')
        self.invocations = []

    def add_invocation(self, return_value, f, args, kwargs):
        i = {'return_value': return_value, 'f': f, 'args': args, 'kwargs': kwargs}
        self.invocations.append(i)

    def __enter__(self):
        self.enter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exit()

    def edit_module_functions(self, items, module):
        for fn_name, fn in items:
            if fn == self.edit_module_functions:
                continue
            fn_module = get_module(fn.__module__)
            if not self.is_module_allowed(fn_module):
                logger.log(log_level, f'skipping {fn_module}.{fn.__name__}')
                continue
            if fn_name.startswith('pytest_') and fn.__module__ == 'conftest' or fn.__module__.endswith('.conftest'):
                logger.log(log_level, f'skipping pytest function {fn} in conftest')
                continue
            logger.log(log_level, f'editing {fn_name} {module} ({fn.__module__}.{fn.__name__})')
            new_item = mergeFunctionMetadata(fn, self.record_test_data(fn))
            setattr(module, fn.__name__, new_item)

    def record_test_data(self, f):
        this = self
        logger.log(log_level, f'wrapping {f}')
        if getattr(f, pytestcleanup_decorated_with_record_test_data, False):
            return f
        if f in [self.record_test_data]:
            return f

        clazz = get_class_that_defined_method(f)
        argspec = inspect.getfullargspec(f)
        is_cls_function = False
        if argspec:
            arg_signature = argspec.args
            is_cls_function = clazz and arg_signature and arg_signature[0] == 'cls'

        def edit_args(args):
            if is_cls_function:
                if len(args) and not isinstance(list(args)[0], clazz):
                    args = add_class_object_as_arg(args)
                elif not len(args):
                    args = tuple([clazz] + list(args))
            return args

        @functools.wraps(f)
        def sync_wrapper(*args, **kwargs):
            logger.log(log_level, f'wrapped {f}')
            args = edit_args(args)
            try:
                return_value = f(*args, **kwargs)
            except (KeyError, ModuleNotFoundError, TypeError, AttributeError) as e:
                # e.g KeyError: 'tkinter'
                # e.g ModuleNotFoundError: No module named 'tkinter'
                # e.g TypeError: unsupported callable
                # e.g 'method_descriptor' object has no attribute '__module__'

                # print(clazz, f, get_module(clazz or f))
                logger.exception(e)
                return

            this.add_invocation(return_value, f, args, kwargs)
            return return_value

        @functools.wraps(f)
        async def async_wrapper(*args, **kwargs):
            # logger.trace(f'wrapped {f}')
            args = edit_args(args)
            try:
                return_value = await f(*args, **kwargs)
            except (KeyError, ModuleNotFoundError, TypeError, AttributeError) as e:
                # e.g KeyError: 'tkinter'
                # e.g ModuleNotFoundError: No module named 'tkinter'
                # e.g TypeError: unsupported callable
                # e.g 'method_descriptor' object has no attribute '__module__'

                # print(clazz, f, get_module(clazz or f))
                logger.exception(e)
                return

            this.add_invocation(return_value, f, args, kwargs)
            return return_value

        def add_class_object_as_arg(args):
            return tuple([clazz] + list(args))

        wrapper = async_wrapper if is_async_fn(f) else sync_wrapper
        wrapper.pytestcleanup_decorated_with_record_test_data = True
        return wrapper

    def enter(self):
        self.edit_module_level_functions()
        self.edit_module_level_classes()
        logger.log(log_level, 'Start recording invocations')

    def edit_module_level_classes(self):
        for name, module in get_loaded_modules():
            logger.log(log_level, f'loading {name}')
            if not self.is_module_allowed(module):
                continue
            try:
                classes = inspect.getmembers(module, inspect.isclass) or []
            except Exception as e:
                logger.warning(f'Failed getting members for module {module}, skipping')
                logger.error(e)
                continue
            # TODO: patch parent class methods
            # TODO: what if a module imported a class from another module?

            for class_name, clazz in classes:
                # clazz = class_tuple[1]
                if clazz == self.__class__:
                    continue
                if issubclass(clazz, Thread):
                    logger.log(log_level, 'skipping thread classes')
                    continue
                if not self.is_module_allowed(get_module(clazz.__module__)):
                    continue
                self.edit_class_function(class_name, clazz)

    def edit_class_function(self, class_name, clazz):
        fn_name: str
        for fn_name, fn in clazz.__dict__.items():
            if not is_regular_function(fn):
                continue
            if fn_name.startswith('__'):  # and fn_name != '__init__':
                continue
            if get_module(fn) == 'tests' and fn_name in ['tearDown', 'setUp']:
                continue
            if inspect.isbuiltin(fn):
                continue
            if is_test_class(clazz) and fn_name in ['setUp', 'tearDown']:
                logger.log(log_level, f'Skipping test function in class {clazz}')
                continue
            logger.log(log_level, f'editing {get_module(clazz.__module__)}.{class_name}.{fn_name}')
            if not hasattr(fn, '__name__') and hasattr(fn, '__func__'):
                # logger.log(log_level, dir(fn.__func__))
                fn = fn.__func__
            try:
                new_item = mergeFunctionMetadata(fn, self.record_test_data(fn))
            except Exception as e:
                logger.error(e)
                raise  # continue
            # TODO: if not being able to recreate method properly, can check how boto3 does it
            try:
                setattr(clazz, fn_name, new_item)
            except Exception as e:
                logger.error(e)
                continue

    def edit_module_level_functions(self):
        for name, module in get_loaded_modules():
            logger.log(log_level, f'loading {name}')
            if not self.is_module_allowed(module):
                continue
            try:
                items = inspect.getmembers(module, inspect.isfunction)
            except Exception as e:
                # I saw this could happen when in debug mode
                logger.warning(f'Failed getting members for module {module}, skipping')
                logger.error(e)
                continue
            logger.log(log_level, f'allowing module {module}')
            self.edit_module_functions(items, module)

    @staticmethod
    def match_in_modules(module_name, modules):
        for item in modules:
            if fnmatch(module_name, item):
                return True

    @classmethod
    def is_module_explicitly_allowed(cls, module_name):
        return cls.match_in_modules(module_name, include_modules)

    @classmethod
    def is_module_explicitly_disallowed(cls, module_name):
        return cls.match_in_modules(module_name, exclude_modules)

    def is_module_allowed(self, module):
        if allow_all_modules:
            return True
        module_name = get_name(module)
        if module_name == '__main__':
            logger.log(log_level, 'Skipping __main__ module as main module will be a different one at run time')
            return
        if self.is_module_explicitly_disallowed(module_name):
            logger.log(log_level, f'Module explicitly disallowed: {module}')
            return
        if self.is_module_explicitly_allowed(module_name):
            logger.log(log_level, f'Module explicitly allowed: {module}')
            return True
        if module_name.startswith('pytest_cleanup'):
            logger.log(log_level, 'Excluding the recorder itself')
            return
        if module_name.startswith('py.'):
            logger.log(log_level, 'Skipping modules starting with py.')
            return
        # if 'pytest' in module_name:
        #     logger.log(log_level, 'Excluding pytest and its plugins')
        #     return
        if 'pydev' in module_name or 'py.builtin' in module_name or 'helpers/pycharm/' in get_file(module):
            logger.log(log_level, 'Excluding debugger modules')
            return
        if is_site_package(module):
            logger.log(log_level, f'excluding site package {module}')
            return
        if exclude_importers(module):
            logger.log(log_level, f'excluding importer {module}')
            return
        if is_system_package(module):
            logger.log(log_level, f'excluding system module {module}')
            return
        return True

    def exit(self):
        logger.log(log_level, f'Stopped recording invocations, got {len(self.invocations)} of them.')
        invocation_group = group_by_function(self.invocations)
        print_invocation_group_summary(invocation_group)
        save_example_scripts()
        self.save_test_data(invocation_group)

    def save_test_data(self, invocation_group):
        for fn, invocations in invocation_group.items():
            module = inspect.getmodule(fn)
            if not self.is_module_allowed(module):
                # maybe it was loaded afterwards! How to handle such cases?
                logger.log(log_level, f'{module} was previously disallowed')
                continue
            module_name = fn.__module__
            clazz = get_class_that_defined_method(fn)
            logger.log(log_level, f'{module_name}.{get_name(fn)}')

            test_cases = [
                {
                    'args': try_dump_dill(x['args']),
                    'kwargs': try_dump_dill(x['kwargs']),
                    'return_value': try_dump_dill(x['return_value']),
                }
                for x in invocations
            ]
            test_cases = remove_duplicate_cases(test_cases)
            write_data_file(module_name, module, clazz, fn, test_cases)


@log_error
def write_data_file(module_name, module, clazz, fn, test_cases):
    function_name = fn.__name__
    if not test_cases:
        return
    class_or_module_name = get_name(clazz) or module_name
    subdir = f'{module_name}/{class_or_module_name}/{function_name}'
    create_directory(subdir)

    success = False
    contents = serialise(module, clazz, fn, test_cases)
    if len(contents) > filesize_limit:
        logger.log(log_level, 'Content is bigger than configured filesize limit')
        return
    for i in range(filename_count_limit):
        filename = get_test_data_filename(subdir, f'{i + 1:02}')
        filepath = abspath(filename)
        if os.path.exists(filepath):
            logger.log(log_level, f'{filename} already exists, skipping.')
            continue
        logger.log(log_level, f'Writing data file at {filepath} ({len(contents)})')
        with open(filepath, 'w') as f:
            f.write(contents)
            success = True
            break
    if not success:
        logger.error(
            f'Could not save test data for function {module_name}.{function_name}, e.g at {filename}. Merge existing test case files or delete them and try again.'
        )


def serialise(module, clazz, fn, test_cases):
    return serialise_json(module, clazz, fn, test_cases)


def serialise_json(module, clazz, fn, test_cases):
    import jsonpickle
    import json

    encoded = jsonpickle.encode(
        {'test_cases': test_cases, 'class': clazz, 'module': module, 'function': fn}, max_depth=serialisation_depth
    )
    # loads/dumps is a terrible workaround to pretty print the json
    pretty = json.dumps(json.loads(encoded), indent=2, sort_keys=True)
    return pretty


def create_directory(sub_dir):
    from os import makedirs

    try:
        makedirs(os.path.join(test_data_directory, sub_dir))
    except Exception as e:
        logger.log(log_level, e)
