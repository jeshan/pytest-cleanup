"""A simple cli-based recorder for Python"""

__version__ = '0.1'

from .recorder import Recorder, get_test_data_filename, user_function
from .runtime import parametrize_stg_tests

__all__ = ['parametrize_stg_tests', 'Recorder', 'get_test_data_filename', 'user_function']
