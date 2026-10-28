import gc
import weakref

import pytest

import j1939


class Listener:
    def callback(self, *args):
        pass


@pytest.mark.parametrize("stream", ["request", "acknowledge"])
def test_unsubscribe_releases_bound_listener(stream):
    ca = j1939.ControllerApplication(j1939.Name())
    listener = Listener()
    listener_ref = weakref.ref(listener)
    getattr(ca, "subscribe_" + stream)(listener.callback)

    # A fresh bound-method object must identify the same subscription.
    getattr(ca, "unsubscribe_" + stream)(listener.callback)
    del listener
    gc.collect()

    assert listener_ref() is None


@pytest.mark.parametrize("stream", ["request", "acknowledge"])
def test_unsubscribe_preserves_other_listener(stream):
    ca = j1939.ControllerApplication(j1939.Name())
    first = Listener()
    second = Listener()
    first_ref = weakref.ref(first)
    second_ref = weakref.ref(second)
    subscribe = getattr(ca, "subscribe_" + stream)
    unsubscribe = getattr(ca, "unsubscribe_" + stream)
    subscribe(first.callback)
    subscribe(second.callback)

    unsubscribe(first.callback)
    del first, second
    gc.collect()

    assert first_ref() is None
    assert second_ref() is not None

    unsubscribe(second_ref().callback)
    gc.collect()
    assert second_ref() is None


@pytest.mark.parametrize("stream", ["request", "acknowledge"])
def test_unsubscribe_removes_one_duplicate_registration(stream):
    ca = j1939.ControllerApplication(j1939.Name())
    listener = Listener()
    listener_ref = weakref.ref(listener)
    subscribe = getattr(ca, "subscribe_" + stream)
    unsubscribe = getattr(ca, "unsubscribe_" + stream)
    subscribe(listener.callback)
    subscribe(listener.callback)

    unsubscribe(listener.callback)
    del listener
    gc.collect()
    assert listener_ref() is not None

    unsubscribe(listener_ref().callback)
    gc.collect()
    assert listener_ref() is None


@pytest.mark.parametrize("stream", ["request", "acknowledge"])
def test_unsubscribe_absent_listener_matches_request_contract(stream):
    ca = j1939.ControllerApplication(j1939.Name())
    listener = Listener()

    with pytest.raises(ValueError):
        getattr(ca, "unsubscribe_" + stream)(listener.callback)
