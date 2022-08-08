import os
import shutil

import pytest

test_cassettes_folder = "tests/cassettes"


#
# ensure the cassettes folder used for testing is cleared
#
@pytest.fixture(scope="session")
def clear_cassettes():
    if os.path.isdir(test_cassettes_folder):
        shutil.rmtree(test_cassettes_folder)
    yield
