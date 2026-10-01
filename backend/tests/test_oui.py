from pathlib import Path

from app.intel.oui import OuiRegistry

FIXTURE = Path(__file__).parent / "fixtures" / "oui_sample.csv"


def test_vendor_lookup_from_csv():
    registry = OuiRegistry.from_csv(FIXTURE)
    assert len(registry) == 2
    assert registry.vendor("00:00:5e:00:53:10") == "ICANN, IANA Department"
    assert registry.vendor("00-00-5E-00-53-99") == "ICANN, IANA Department"


def test_private_mac_has_no_vendor():
    assert OuiRegistry.from_csv(FIXTURE).vendor("02:00:5E:00:53:10") is None


def test_unknown_or_invalid_mac():
    registry = OuiRegistry.from_csv(FIXTURE)
    unknown = ":".join(["00", "00", "5F", "00", "53", "10"])
    assert registry.vendor(unknown) is None
    assert registry.vendor("not a mac") is None


def test_missing_file_gives_empty_registry(tmp_path):
    assert len(OuiRegistry.from_csv(tmp_path / "missing.csv")) == 0
