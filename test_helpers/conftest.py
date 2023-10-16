import pytest

from test_helpers.feeder import Feeder

@pytest.fixture()
def feeder():
    #setup
    feeder = Feeder()
    yield feeder
    #teardown
    feeder.stop()