import os

from loguru import logger


def get_test_data_directory(parent_dir):
    sub_dir = os.environ.get('PYTESTCLEANUP_TEST_DATA_DIRECTORY', 'test-data')
    return os.path.join(parent_dir, sub_dir)


def get_test_dir():
    result = os.environ.get('PYTESTCLEANUP_TEST_DIRECTORY')
    if not result:
        for item in ['test', 'tests', 'testing', '.']:
            if os.path.isdir(item):
                result = item
                break
    logger.debug(f'Will place {test_filename} under {os.path.abspath(result)}')
    return result


test_filename = 'test_pytestcleanup_cases.py'
test_directory = get_test_dir()
test_data_directory = get_test_data_directory(test_directory)
filename_count_limit = 10
