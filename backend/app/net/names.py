import re
import unicodedata

_INVALID = re.compile(r"[^a-z0-9-]+")
MAX_LEN = 63


def hostname_for(name: str, taken: set[str]) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = _INVALID.sub("-", ascii_name.lower()).strip("-")
    base = re.sub(r"-{2,}", "-", base)[:MAX_LEN].strip("-") or "device"
    candidate, n = base, 2
    while candidate in taken:
        suffix = f"-{n}"
        candidate = base[: MAX_LEN - len(suffix)].rstrip("-") + suffix
        n += 1
    return candidate
