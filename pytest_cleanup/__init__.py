"""Automated, comprehensive and well-organised pytest test cases."""

import os

from .recorder import Recorder, get_test_data_filename, user_function
from .runtime import parametrize_stg_tests

__version__ = os.environ.get('VERSION', 'local')

__all__ = ['parametrize_stg_tests', 'Recorder', 'get_test_data_filename', 'user_function']
