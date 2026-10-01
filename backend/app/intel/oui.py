import csv
import re
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.net.mac import is_private_mac, normalize_mac

HEX6 = re.compile(r"^[0-9A-F]{6}$")


class OuiRegistry:
    def __init__(self, entries: dict[str, str]) -> None:
        self._entries = entries

    @classmethod
    def from_csv(cls, path: Path) -> "OuiRegistry":
        entries: dict[str, str] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                for row in csv.DictReader(handle):
                    assignment = (row.get("Assignment") or "").strip().upper()
                    name = (row.get("Organization Name") or "").strip()
                    if HEX6.match(assignment) and name:
                        entries[assignment] = name
        return cls(entries)

    def __len__(self) -> int:
        return len(self._entries)

    def vendor(self, mac: str) -> str | None:
        try:
            normalized = normalize_mac(mac)
        except ValueError:
            return None
        if is_private_mac(normalized):
            return None
        return self._entries.get(normalized.replace(":", "")[:6])


@lru_cache(maxsize=1)
def default_registry() -> OuiRegistry:
    return OuiRegistry.from_csv(Path(settings.oui_path))
