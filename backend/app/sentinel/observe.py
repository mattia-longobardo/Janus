from dataclasses import dataclass
from typing import Any

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.l2 import ARP

from app.net.mac import normalize_mac

NO_IP = "0.0.0.0"
DHCP_CLIENT_TYPES = {1, 3, 8}


@dataclass(frozen=True)
class Observation:
    mac: str
    ip: str | None
    source: str
    hostname: str | None = None
    vendor_class: str | None = None
    param_list: tuple[int, ...] = ()

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.hostname:
            data["hostname"] = self.hostname
        if self.vendor_class:
            data["vendor_class"] = self.vendor_class
        if self.param_list:
            data["param_list"] = list(self.param_list)
        return data


def _text(value: object) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        return None
    cleaned = value.replace("\x00", "").strip()
    return cleaned[:255] or None


def from_arp(packet: Any) -> Observation | None:
    if ARP not in packet:
        return None
    arp = packet[ARP]
    if arp.op not in (1, 2):
        return None
    try:
        mac = normalize_mac(str(arp.hwsrc))
    except ValueError:
        return None
    ip = arp.psrc if arp.psrc and arp.psrc != NO_IP else None
    return Observation(mac, ip, "arp")


def from_dhcp(packet: Any) -> Observation | None:
    if BOOTP not in packet or DHCP not in packet or packet[BOOTP].op != 1:
        return None
    options: dict[str, Any] = {}
    for option in packet[DHCP].options:
        if isinstance(option, tuple) and len(option) >= 2:
            options[option[0]] = option[1] if len(option) == 2 else list(option[1:])
    if options.get("message-type") not in DHCP_CLIENT_TYPES:
        return None
    try:
        mac = normalize_mac(bytes(packet[BOOTP].chaddr)[:6].hex())
    except ValueError:
        return None
    ciaddr = packet[BOOTP].ciaddr
    requested = options.get("requested_addr")
    ip = requested if requested and requested != NO_IP else (ciaddr if ciaddr and ciaddr != NO_IP else None)
    params = options.get("param_req_list") or []
    if isinstance(params, int):
        params = [params]
    return Observation(
        mac,
        str(ip) if ip else None,
        "dhcp",
        _text(options.get("hostname")),
        _text(options.get("vendor_class_id")),
        tuple(int(p) for p in params),
    )


def observe(packet: Any) -> Observation | None:
    return from_dhcp(packet) or from_arp(packet)
