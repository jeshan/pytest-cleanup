import functools
import inspect
import os
from glob import glob
from random import shuffle
from types import GeneratorType
from typing import TextIO

from _pytest.python import Metafunc
from loguru import logger

from pytest_cleanup.common import (
    get_class_that_defined_method,
    mergeFunctionMetadata,
    is_async_fn,
    try_load_dill,
    pytestcleanup_decorated_with_record_test_data,
    get_name,
)
from pytest_cleanup.constants import test_data_directory


def deserialise(f):
    return deserialise_json(f)


def deserialise_json(f: TextIO):
    import jsonpickle

    contents = f.read()
    return jsonpickle.loads(contents)


def transform_function(f):
    if getattr(f, pytestcleanup_decorated_with_record_test_data, False):
        # raise Exception('Already decorated')
        return f

    clazz = get_class_that_defined_method(f)

    arg_signature = inspect.getfullargspec(f).args
    is_cls_function = clazz and arg_signature and arg_signature[0] == 'cls'

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if is_cls_function:
            first_arg_is_cls = len(args) and not isinstance(list(args)[0], clazz) or not len(args)
            if first_arg_is_cls:
                args = remove_first_argument(args)
        return_value = f(*args, **kwargs)
        if isinstance(return_value, GeneratorType):
            # generators aren't really comparable, so we compare lists instead
            return list(return_value)
        return return_value

    def remove_first_argument(args):
        return tuple(list(args)[1:])

    wrapper.pytestcleanup_decorated_with_record_test_data = True
    return wrapper


def deserialise_from_file(filename):
    with open(filename, 'r') as f:
        try:
            return deserialise(f)
        except Exception as e:
            logger.error(f'Error loading data file {filename}')
            logger.error(e)


def load_data_file(filename, is_async):
    data = deserialise_from_file(filename)
    if not data:
        return
    fn = data['function']
    if (is_async and not is_async_fn(fn)) or (not is_async and is_async_fn(fn)):
        return
    if not fn:
        logger.warning(f'Function was not properly loaded from {filename}')
        return
    module = data['module']
    function_name = fn.__name__

    clazz = data['class']
    class_or_module = clazz or module
    if not class_or_module:
        # can happen if user loaded std lib modules
        return
        # raise Exception(f'no class or module found for {filename}')
    fn = getattr(class_or_module, function_name)
    new_item = mergeFunctionMetadata(fn, transform_function(fn))

    return (
        module,
        clazz,
        [
            (new_item, try_load_dill(x['args']), try_load_dill(x['kwargs']), edit_return_value(x['return_value']))
            for x in data['test_cases']
        ],
    )


def edit_return_value(return_value):
    from _collections_abc import list_iterator

    return_value = try_load_dill(return_value)

    if isinstance(return_value, list_iterator):
        # because jsonpickle serialises things like generators as "list iterators"
        return_value = list(return_value)
    return return_value


def parametrize_stg_tests(metafunc: Metafunc):
    if metafunc.definition.name == 'test_pytest_cleanup_async_test_cases':
        _parametrize_stg_tests(metafunc, is_async=True)
    if metafunc.definition.name == 'test_pytest_cleanup_sync_test_cases':
        _parametrize_stg_tests(metafunc, is_async=False)


def _parametrize_stg_tests(metafunc: Metafunc, is_async):
    sep = os.sep
    path_list = list(sorted(glob(f'{test_data_directory}{sep}*{sep}**{sep}*.json', recursive=True)))
    all_test_data = []
    all_ids = []
    for data_file_path in path_list:
        split = data_file_path.split(sep)
        function_name = split[-2]
        try:
            tuple_result = load_data_file(data_file_path, is_async)
            if tuple_result:
                module, clazz, test_cases = tuple_result
            else:
                continue
        except Exception as e:
            logger.error(f'Could not load data file {data_file_path}')
            logger.error(e)
            raise e
        module_name = get_name(module)
        class_name = get_name(clazz)
        class_or_module_name = module_name if module_name != class_name else f'{module_name}.{class_name}'
        ids = [f'{class_or_module_name}-{function_name}'] * len(test_cases)
        all_test_data.extend(test_cases)
        all_ids.extend(ids)
    metafunc.parametrize(['fn', 'args', 'kwargs', 'expected'], all_test_data, ids=all_ids)
