# pytest_cleanup
> Automated, comprehensive and well-organised pytest test cases.

Get started by typing `pip install pytest_cleanup`

# Description
> If we like to format our code with tools like Black, then why don't we do the same with our tests?

TLDR: `pytest_cleanup` runs your Python code and generates pytest tests out of it.

This will help you reach broad test coverage with real-world test cases.
Tests that are generated "just work", i.e they are clean, unaware of implementation details, and don't require active maintenance.

It even generates the (minimal) code that it requires to work; just 2 test functions (one for async and another for normal functions). These 2 are then parameterised with the [parametrize](https://docs.pytest.org/en/latest/parametrize.html) feature via `pytest_generate_tests`.

The data files are written with `jsonpickle` and look like this:
![](images/example-data-file.png)

It's also possible to run it against an existing pytest test suite (see below).

In other words, it lets you do DDT for pytest (data-driven tests, development-driven testing, or both :nerd_face:)

# Why would you bother?

- save time by having tests generated for you :tada:
- dramatically increase test code coverage with little effort
- write more maintainable tests by separating code and data
- Too tedious/hard to generate custom data for your application? Run your code like you would in production and data files will be generated.
- helps you organise your test code consistently in new projects, or:
- replace your existing disorganised test code :+1:
- reduces handwritten setup code
- accelerate your migration to pytest; Since pytest supports existing nose and unittest, enable the recorder, run pytest and `pytest_cleanup` will generate clean tests for you.


> Note that tests that you write manually can still be kept or made to follow the same conventions as pytest_cleanup for consistency

# How it works

`pytest_cleanup` generates 3 files. These contain the minimal boilerplate required in your test (or current) directory:

```
2020-01-25 15:36:34.614 | DEBUG    | pytest_cleanup.constants:get_test_dir:18 - Will place test_pytestcleanup_cases.py under /app/test
2020-01-25 15:36:34.614 | INFO     | pytest_cleanup.recorder:__init__:252 - creating instance of recorder
2020-01-25 15:36:34.692 | DEBUG    | pytest_cleanup.recorder:save_example_scripts:159 - Saving example scripts (test_pytestcleanup_cases.py, conftest-pytest-cleanup-runtime.py, conftest-pytest-cleanup-record.py) under test
```

## test_pytestcleanup_cases.py

This will have the following 2 tests:
```python
import pytest

from pytest_cleanup.common import assert_return_values

def test_pytest_cleanup_sync_test_cases(fn, args, kwargs, expected):
    """See test/test-data directory for test cases"""
    actual = fn(*args, **kwargs)
    assert_return_values(actual, expected)


@pytest.mark.asyncio
async def test_pytest_cleanup_async_test_cases(fn, args, kwargs, expected):
    """See test/test-data directory for test cases.
    support for asyncio in pytest may be enabled by installing pytest-asyncio """
    actual = await fn(*args, **kwargs)
    assert_return_values(actual, expected)
```

## conftest-pytest-cleanup-runtime.py

The latter will be parametrized with the data files that will be generated later under `$your_test_directory/test-data`. This is achieved with snippet found with the also generated: `conftest-pytest-cleanup-runtime.py` (rename it to conftest.py or merge it with your existing conftest.py so that pytest can load it):

```python
def pytest_generate_tests(metafunc):
    from pytest_cleanup import parametrize_stg_tests

    parametrize_stg_tests(metafunc)

```


## conftest-pytest-cleanup-record.py (optional)

The third file that is generated is `conftest-pytest-cleanup-record.py`. You can use this one in case you want to use `pytest_cleanup` against an existing pytest test suite (see previous section on why you might want that):

> Again, rename it to conftest.py or merge it with your existing conftest.py so that pytest can load it

```python
from pytest_cleanup import Recorder


def pytest_runtestloop(session):
    Recorder().enter()


def pytest_sessionfinish(session, exitstatus):
    Recorder().exit()
```


# Usage
There are 3 ways to use `pytest_cleanup`:
## Basic usage
1. Record your tests `python -m pytest_cleanup your.module.path` (an importable module path, not file path!). This will attempt to call a no-arg function named `main` in the module specified. (Function name configurable; see [configuration](#configuration) section). `pytest_cleanup` will record function invocations and save them `$test_directory/test-data`.
2. Put generated `conftest-pytest-cleanup-runtime.py` into your conftest.py
3. Run pytest as you normally would.  It will load generated data by step 1 under `$test_directory/test-data` and dynamically generate test cases from it.
4. Confirm your test run passes.

## Use as a library
`pytest_cleanup` can also be used as a library for more flexibility. Otherwise, it's only needed as a test dependency.

```python
from pytest_cleanup import Recorder

with Recorder():
    your_custom_code_here()
```

Run pytest as explained in previous subsection.

> Note that the `Recorder` object is a singleton and invoking `Recorder()` multiple times has no effect.

## Using while running pytest
You can also run `pytest_cleanup` against an existing test suite:
1. `python -m pytest_cleanup`
2. Put generated `conftest-pytest-cleanup-record.py` into your conftest.py. (it has the functions `pytest_runtestloop` and `pytest_sessionfinish` to be able to record in pytest sessions)
3. Run pytest as you normally would
4. In conftest.py, replace `pytest_runtestloop` and `pytest_sessionfinish` functions by the contents of `conftest-pytest-cleanup-runtime.py` (which has the `pytest_generate_tests` function)

# Release process
Deployment pipeline described in [templates/deployment-pipeline.yaml](templates/deployment-pipeline.yaml).

Project can also be released with:
- `docker-compose run release` : Enter password when prompted


# Copyright
Released under the MIT licence. See file named [LICENCE](LICENCE) for details.

