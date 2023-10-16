import pytest

from feeder import Feeder

@pytest.fixture()
def feeder():
    #setup
    feeder = Feeder()
    yield feeder
    #teardown
    feeder.stop()