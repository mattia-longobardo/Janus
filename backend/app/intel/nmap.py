import xml.etree.ElementTree as ET
from dataclasses import dataclass

TELNET = ("high", "Telnet sends passwords in clear text")
R_SERVICES = ("high", "Legacy r-services allow password-less remote login")
FTP = ("warning", "FTP sends passwords in clear text")
VNC = ("warning", "VNC remote desktop is reachable on the LAN")
RDP = ("warning", "Windows Remote Desktop is reachable on the LAN")
DATABASE = ("warning", "A database port is reachable on the LAN")
UPNP = ("warning", "UPnP control port is reachable: devices can change router settings")

RISKY_PORTS: dict[int, tuple[str, str]] = {
    23: TELNET, 2323: TELNET, 512: R_SERVICES, 513: R_SERVICES, 514: R_SERVICES, 21: FTP,
    5900: VNC, 5901: VNC, 3389: RDP,
    1433: DATABASE, 3306: DATABASE, 5432: DATABASE, 6379: DATABASE, 9200: DATABASE, 11211: DATABASE, 27017: DATABASE,
}
RISKY_NAMES: dict[str, tuple[str, str]] = {
    "telnet": TELNET, "login": R_SERVICES, "shell": R_SERVICES, "exec": R_SERVICES, "ftp": FTP, "vnc": VNC,
    "ms-wbt-server": RDP, "mysql": DATABASE, "postgresql": DATABASE,
    "redis": DATABASE, "mongodb": DATABASE, "ms-sql-s": DATABASE, "memcached": DATABASE, "elasticsearch": DATABASE,
    "upnp": UPNP,
}


@dataclass(frozen=True)
class PortResult:
    port: int
    proto: str
    service: str | None
    version: str | None


def parse_nmap_xml(xml: str) -> list[PortResult]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"unreadable nmap output: {exc}") from exc
    hosts = list(root.iter("host"))
    if not hosts or any((h.find("status") is None or h.find("status").get("state") != "up") for h in hosts):
        raise ValueError("host is down or did not answer")
    if any(h.get("timedout") == "true" for h in hosts):
        raise ValueError("host timed out before the scan completed")
    results = []
    for port in root.iter("port"):
        state = port.find("state")
        if state is None or state.get("state") != "open":
            continue
        service = port.find("service")
        name = service.get("name") if service is not None else None
        parts = [service.get(key) for key in ("product", "version", "extrainfo")] if service is not None else []
        version = " ".join(part for part in parts if part) or None
        results.append(PortResult(int(port.get("portid", "0")), port.get("protocol", "tcp"), name, version))
    return results


def classify(port: int, service: str | None) -> tuple[str, str | None]:
    match = RISKY_NAMES.get((service or "").lower()) or RISKY_PORTS.get(port)
    return match if match else ("none", None)
