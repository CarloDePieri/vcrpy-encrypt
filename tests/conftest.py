import os
from typing import Callable

import pytest
import shutil

from time import sleep

test_cassettes_folder = "tests/cassettes"


#
# ensure the cassettes folder used for testing is cleared
#
@pytest.fixture(scope="session")
def clear_cassettes():
    if os.path.isdir(test_cassettes_folder):
        shutil.rmtree(test_cassettes_folder)
    yield


def _wait_for(condition: Callable[[], bool], wait_timeout: int = 3) -> bool:
    """
    A helper function that waits for a condition to be met or a timeout to be reached.

    :param condition: A function that return a boolean
    :param wait_timeout: The max time to wait for the condition to be met
    :return: True if the condition was met, False if the timeout was reached
    """
    step = 0.05
    while not condition():
        sleep(step)
        wait_timeout -= step
        if wait_timeout <= 0:
            return False
    return True


#
# A wrapper around os.path.isfile that only fails if the file still doesn't exist after a timeout.
# Slow ci systems might need this, since the file produced by tests takes longer to be written than the test itself.
#
@pytest.fixture
def is_file():
    def _wait_for_file(file_path: str, wait_timeout: int = 3) -> bool:
        return _wait_for(lambda: os.path.isfile(file_path), wait_timeout)
    return _wait_for_file


#
# A wrapper around os.path.isfile that only fails if the file still exist after a timeout.
# Slow ci systems might need this, since the file produced by tests takes longer to be deleted than the test itself.
#
@pytest.fixture
def is_not_file():
    def _wait_for_no_file(file_path: str, wait_timeout: int = 3) -> bool:
        return _wait_for(lambda: not os.path.isfile(file_path), wait_timeout)
    return _wait_for_no_file
