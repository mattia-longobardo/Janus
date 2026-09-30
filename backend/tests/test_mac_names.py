import pytest

from app.net.mac import is_private_mac, normalize_mac, oui
from app.net.names import hostname_for


@pytest.mark.parametrize("raw", ["00:00:5e:00:53:10", "00-00-5E-00-53-10", "00005E005310", " 00:00:5E:00:53:10 "])
def test_normalize_mac_accepts_common_formats(raw):
    assert normalize_mac(raw) == "00:00:5E:00:53:10"


@pytest.mark.parametrize("raw", ["", "00:00:5E:00:53", "zz:00:5E:00:53:10", "00:00:5E:00:53:10:11"])
def test_normalize_mac_rejects_garbage(raw):
    with pytest.raises(ValueError):
        normalize_mac(raw)


@pytest.mark.parametrize("first_octet", ["02", "06", "0A", "0E", "fe"])
def test_private_mac_uses_locally_administered_bit(first_octet):
    assert is_private_mac(first_octet + ":00:5E:00:53:11") is True


@pytest.mark.parametrize("first_octet", ["00", "04", "08", "fc"])
def test_universal_mac_is_not_private(first_octet):
    assert is_private_mac(first_octet + ":00:5E:00:53:11") is False


def test_oui():
    assert oui("00-00-5e-00-53-10") == "00:00:5E"


def test_hostname_is_dns_safe():
    assert hostname_for("PM_FRIGO", set()) == "pm-frigo"
    assert hostname_for("Portable Knob", set()) == "portable-knob"
    assert hostname_for("Café Été", set()) == "cafe-ete"
    assert hostname_for("___", set()) == "device"


def test_hostname_collisions_get_suffix_and_stay_short():
    taken = {"tv", "tv-2"}
    assert hostname_for("TV", taken) == "tv-3"
    long_name = "x" * 80
    first = hostname_for(long_name, set())
    assert len(first) == 63
    second = hostname_for(long_name, {first})
    assert len(second) == 63 and second.endswith("-2")
