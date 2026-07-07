"""Tests for the SAE J1939-73 SPN conversion methods (CM 1, 2, 3, 4)."""
import pytest

from j1939.diagnostic_messages import DTC


@pytest.mark.parametrize("cm", [1, 2, 3, 4])
@pytest.mark.parametrize("spn", [0, 123, 456, 0x12345, 0x3FFFF])
@pytest.mark.parametrize("fmi", [0, 1, 5, 31])
@pytest.mark.parametrize("oc", [0, 1, 42, 127])
def test_dtc_round_trip(cm, spn, fmi, oc):
    """Encoded DTC bytes must decode back to the same SPN/FMI/OC/CM."""
    encoded = DTC(spn=spn, fmi=fmi, oc=oc, cm=cm)
    decoded = DTC(dtc=encoded.dtc, cm=cm)
    assert decoded.spn == spn
    assert decoded.fmi == fmi
    assert decoded.oc == oc
    assert decoded.cm == cm


@pytest.mark.parametrize("cm,expected_cm_bit", [(1, 1), (2, 1), (3, 1), (4, 0)])
def test_cm_bit_on_wire(cm, expected_cm_bit):
    """Only CM 4 has the CM bit cleared; CMs 1/2/3 set it."""
    d = DTC(spn=1000, fmi=5, oc=3, cm=cm)
    assert ((d.dtc >> 31) & 0x01) == expected_cm_bit


def test_cm1_byte_layout_matches_reference():
    """CM 1 layout: b1=SPN[18:11], b2=SPN[10:3], b3=SPN[2:0]|FMI, b4=OC|CM."""
    spn, fmi, oc = 0x12345, 5, 3
    d = DTC(spn=spn, fmi=fmi, oc=oc, cm=1)
    b1 = d.dtc & 0xFF
    b2 = (d.dtc >> 8) & 0xFF
    b3 = (d.dtc >> 16) & 0xFF
    b4 = (d.dtc >> 24) & 0xFF
    assert b1 == (spn >> 11) & 0xFF
    assert b2 == (spn >> 3) & 0xFF
    assert b3 == (((spn & 0x07) << 5) | (fmi & 0x1F))
    assert b4 == ((oc & 0x7F) | 0x80)


def test_cm2_byte_layout_matches_reference():
    """CM 2 layout: b1=SPN[10:3], b2=SPN[18:11], b3=SPN[2:0]|FMI, b4=OC|CM."""
    spn, fmi, oc = 0x12345, 5, 3
    d = DTC(spn=spn, fmi=fmi, oc=oc, cm=2)
    b1 = d.dtc & 0xFF
    b2 = (d.dtc >> 8) & 0xFF
    b3 = (d.dtc >> 16) & 0xFF
    b4 = (d.dtc >> 24) & 0xFF
    assert b1 == (spn >> 3) & 0xFF
    assert b2 == (spn >> 11) & 0xFF
    assert b3 == (((spn & 0x07) << 5) | (fmi & 0x1F))
    assert b4 == ((oc & 0x7F) | 0x80)


@pytest.mark.parametrize("cm", [3, 4])
def test_cm3_cm4_byte_layout(cm):
    """CM 3/4 layout: SPN packed little-endian in b1/b2 with top 3 bits in b3."""
    spn, fmi, oc = 0x12345, 5, 3
    d = DTC(spn=spn, fmi=fmi, oc=oc, cm=cm)
    b1 = d.dtc & 0xFF
    b2 = (d.dtc >> 8) & 0xFF
    b3 = (d.dtc >> 16) & 0xFF
    b4 = (d.dtc >> 24) & 0xFF
    assert b1 == spn & 0xFF
    assert b2 == (spn >> 8) & 0xFF
    assert b3 == ((((spn >> 16) & 0x07) << 5) | (fmi & 0x1F))
    expected_b4 = oc & 0x7F
    if cm == 3:
        expected_b4 |= 0x80
    assert b4 == expected_b4


def test_invalid_cm_raises():
    with pytest.raises(ValueError):
        DTC(spn=1, fmi=1, oc=0, cm=5)
    with pytest.raises(ValueError):
        DTC(dtc=0x12345678, cm=0)


def test_default_cm_is_4():
    """Backward compatibility: omitting `cm` produces the modern CM 4 layout."""
    d = DTC(spn=0x12345, fmi=5, oc=3)
    assert d.cm == 4
    assert ((d.dtc >> 31) & 0x01) == 0
