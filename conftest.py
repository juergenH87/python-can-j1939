import pytest

from test.helpers.feeder import Feeder


@pytest.fixture()
def feeder():
    # setup
    feeder = Feeder()
    try:
        yield feeder
    finally:
        # teardown — guarantee cleanup even if the test raises
        try:
            feeder.stop()
        except Exception:
            pass
