import re

_NON_HEX = re.compile(r"[^0-9A-Fa-f]")
_TWELVE_HEX = re.compile(r"[0-9A-F]{12}")
_SEPARATORS = re.compile(r"^[0-9A-Fa-f:\-.\s]+$")


def normalize_mac(raw: str) -> str:
    raw = (raw or "").strip()
    if not _SEPARATORS.match(raw):
        raise ValueError(f"invalid MAC address: {raw!r}")
    digits = _NON_HEX.sub("", raw).upper()
    if not _TWELVE_HEX.fullmatch(digits):
        raise ValueError(f"invalid MAC address: {raw!r}")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def is_private_mac(mac: str) -> bool:
    return bool(int(normalize_mac(mac)[1], 16) & 0b0010)


def oui(mac: str) -> str:
    return normalize_mac(mac)[:8]
