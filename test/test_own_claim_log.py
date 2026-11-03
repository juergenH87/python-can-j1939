"""Actual listener-to-CA logging and arbitration behavior, no CAN device."""
import logging

import can
import j1939
import pytest


@pytest.fixture
def rig():
    sent = []
    ecu = j1939.ElectronicControlUnit(send_message=lambda *a, **k: sent.append((a, k)))
    name = j1939.Name(arbitrary_address_capable=1, identity_number=100)
    ca = j1939.ControllerApplication(name, 128, bypass_address_claim=True)
    ecu.add_ca(controller_application=ca)
    try:
        yield ecu, ca, sent
    finally:
        ecu.stop()


def incoming(ecu, name, source=128, is_rx=True):
    frame = can.Message(arbitration_id=0x18EEFF00 | source, is_extended_id=True,
                        data=name.bytes, is_rx=is_rx)
    ecu._listeners[0].on_message_received(frame)


def conflicts(caplog):
    return [r for r in caplog.records if "with conflicting address" in r.getMessage()]


@pytest.mark.parametrize("waiting", [False, True])
@pytest.mark.parametrize("is_rx", [False, True])
def test_same_name_claim_does_not_report_contention(rig, caplog, waiting, is_rx):
    ecu, ca, sent = rig
    if waiting:
        ca._device_address_state = ca.State.WAIT_VETO
        ca._device_address = 254
    before = ca.state, ca._device_address, ca._device_address_announced
    with caplog.at_level(logging.INFO):
        incoming(ecu, ca._name, is_rx=is_rx)
    assert (ca.state, ca._device_address, ca._device_address_announced) == before
    assert sent == []
    assert conflicts(caplog) == []


@pytest.mark.parametrize("waiting", [False, True])
@pytest.mark.parametrize("offset", [-1, 1])
def test_real_contender_keeps_log_and_arbitration(rig, caplog, waiting, offset):
    ecu, ca, sent = rig
    if waiting:
        ca._device_address_state = ca.State.WAIT_VETO
        ca._device_address = 254
    peer = j1939.Name(value=ca._name.value + offset)
    with caplog.at_level(logging.INFO):
        incoming(ecu, peer)
    assert len(conflicts(caplog)) == 1
    assert len(sent) == 1
    if offset < 0:
        assert ca.state == ca.State.WAIT_VETO
        assert ca._device_address_announced == 129
    else:
        assert ca.state == (ca.State.WAIT_VETO if waiting else ca.State.NORMAL)
        assert ca._device_address_announced == 128


def test_different_address_is_not_contention(rig, caplog):
    ecu, ca, sent = rig
    with caplog.at_level(logging.INFO):
        incoming(ecu, j1939.Name(value=ca._name.value - 1), source=129)
    assert conflicts(caplog) == []
    assert ca.state == ca.State.NORMAL
    assert sent == []
