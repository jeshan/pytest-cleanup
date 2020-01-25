import inspect
import os

import dill
from loguru import logger

from pytest_cleanup.constants import test_data_directory

log_level = os.environ.get('PYTESTCLEANUP_LOG_LEVEL', 'TRACE')
pytestcleanup_decorated_with_record_test_data = 'pytestcleanup_decorated_with_record_test_data'


def get_test_data_filename(subdir, filename):
    return f'{test_data_directory}/{subdir}/{filename}.json'


def is_async_fn(param):
    import asyncio

    return asyncio.iscoroutinefunction(param)


def get_name(param):
    return param.__name__ if hasattr(param, '__name__') else ''


def get_class_that_defined_method(meth):
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
            if cls.__dict__.get(meth.__name__) is meth:
                return cls
        meth = meth.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        try:
            cls = getattr(inspect.getmodule(meth), meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
        except Exception as e:
            logger.warning(e)
            raise
        if isinstance(cls, type):
            return cls
    return getattr(meth, '__objclass__', None)


def mergeFunctionMetadata(f, g):
    # this function was copied from Twisted core, https://github.com/racker/python-twisted-core
    # licence notice in file ../LICENCE-Twisted-core
    """
    Overwrite C{g}'s name and docstring with values from C{f}.  Update
    C{g}'s instance dictionary with C{f}'s.
    To use this function safely you must use the return value. In Python 2.3,
    L{mergeFunctionMetadata} will create a new function. In later versions of
    Python, C{g} will be mutated and returned.
    @return: A function that has C{g}'s behavior and metadata merged from
        C{f}.
    """
    try:
        g.__name__ = f.__name__
    except TypeError:
        try:
            import types

            merged = types.FunctionType(
                g.func_code, g.func_globals, f.__name__, inspect.getargspec(g)[-1], g.func_closure
            )
        except TypeError:
            pass
    else:
        merged = g
    try:
        merged.__doc__ = f.__doc__
    except (TypeError, AttributeError):
        pass
    try:
        merged.__dict__.update(g.__dict__)
        merged.__dict__.update(f.__dict__)
    except (TypeError, AttributeError):
        pass
    merged.__module__ = f.__module__
    return merged


def is_regular_function(param):
    return inspect.isroutine(param)


def is_function(param):
    import types

    return isinstance(param, (types.FunctionType, types.BuiltinFunctionType, types.MethodType, types.BuiltinMethodType))


def is_local_function(param):
    return (is_regular_function(param) and '<locals>' in param.__qualname__) or is_function(param)


def try_load_dill(param):
    return _try_dill(dill.loads, param)


def try_dump_dill(param):
    return _try_dill(dill.dumps, param)


def unwrap_function(fn):
    if hasattr(fn, pytestcleanup_decorated_with_record_test_data):
        return fn.__wrapped__
    return fn


def _try_dill(dill_fn, param):
    if isinstance(param, tuple):  # is args
        result = []
        for item in param:
            result.append(_try_dill(dill_fn, item))
        return tuple(result)
    if isinstance(param, dict):  # is kwargs
        result = {}
        for k, v in param.items():
            result[k] = _try_dill(dill_fn, v)
        return result
    result = unwrap_function(param)
    if dill_fn == dill.loads or (dill_fn == dill.dumps and is_local_function(param)):
        try:
            result = dill_fn(param)
        except:
            pass
    return result


def assert_return_values(actual, expected):
    if is_function(actual) and is_function(expected):
        assert unwrap_function(actual).__code__ == expected.__code__
        return
    assert actual == expected
