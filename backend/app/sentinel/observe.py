from dataclasses import dataclass
from typing import Any

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS
from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import ARP, Ether

from app.net.mac import normalize_mac

NO_IP = "0.0.0.0"
DHCP_CLIENT_TYPES = {1, 3, 8}
NETBIOS_OWN_NAME_OPCODES = {5, 8, 9}
MODEL_KEYS = (b"md=", b"model=", b"am=", b"ty=", b"usb_MDL=")


@dataclass(frozen=True)
class Observation:
    mac: str
    ip: str | None
    source: str
    hostname: str | None = None
    vendor_class: str | None = None
    param_list: tuple[int, ...] = ()
    services: tuple[str, ...] = ()
    model: str | None = None
    server: str | None = None

    def payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.hostname:
            data["hostname"] = self.hostname
        if self.vendor_class:
            data["vendor_class"] = self.vendor_class
        if self.param_list:
            data["param_list"] = list(self.param_list)
        if self.services:
            data["services"] = list(self.services)
        if self.model:
            data["model"] = self.model
        if self.server:
            data["server"] = self.server
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


def _sender(packet: Any) -> tuple[str, str | None] | None:
    if Ether not in packet or IP not in packet:
        return None
    try:
        mac = normalize_mac(str(packet[Ether].src))
    except ValueError:
        return None
    ip = packet[IP].src
    return mac, (ip if ip and ip != NO_IP else None)


def _name(value: object) -> str:
    text = value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
    return text.rstrip(".")


def from_mdns(packet: Any) -> Observation | None:
    if UDP not in packet or packet[UDP].sport != 5353 or DNS not in packet or packet[DNS].qr != 1:
        return None
    sender = _sender(packet)
    if sender is None:
        return None
    dns = packet[DNS]
    records = list(dns.an or []) + list(dns.ar or [])
    addresses = [record for record in records if record.type == 1]
    if addresses and not any(str(record.rdata) == sender[1] for record in addresses):
        return None
    hostname, model, services = None, None, set()
    for record in records:
        name = _name(record.rrname)
        if record.type == 12 and name.startswith("_") and name.endswith(".local") and "._dns-sd." not in name:
            services.add(name[: -len(".local")])
        elif record.type == 1 and name.endswith(".local") and hostname is None and str(record.rdata) == sender[1]:
            hostname = _text(name[: -len(".local")])
        elif record.type == 16 and model is None:
            for item in record.rdata if isinstance(record.rdata, list) else [record.rdata]:
                raw = item if isinstance(item, bytes) else str(item).encode()
                for key in MODEL_KEYS:
                    if raw.startswith(key):
                        model = _text(raw[len(key):])
                        break
                if model:
                    break
    if not (hostname or model or services):
        return None
    return Observation(sender[0], sender[1], "mdns", hostname, services=tuple(sorted(services)), model=model)


def from_netbios(packet: Any) -> Observation | None:
    if UDP not in packet or packet[UDP].sport != 137:
        return None
    sender = _sender(packet)
    payload = bytes(packet[UDP].payload)
    if sender is None or len(payload) < 45 or payload[12] != 0x20:
        return None
    if (payload[2] >> 3) & 0x0F not in NETBIOS_OWN_NAME_OPCODES:
        return None
    if len(payload) >= 64 and payload[62] & 0x80:
        return None
    encoded = payload[13:45]
    try:
        chars = [chr(((encoded[i] - 65) << 4) | (encoded[i + 1] - 65)) for i in range(0, 32, 2)]
    except ValueError:
        return None
    if chars[15] not in ("\x00", "\x20"):
        return None
    raw_name = "".join(chars[:15]).strip()
    if not raw_name or any(ord(c) < 32 or ord(c) > 126 for c in raw_name):
        return None
    return Observation(sender[0], sender[1], "netbios", _text(raw_name))


def from_ssdp(packet: Any) -> Observation | None:
    if UDP not in packet or packet[UDP].sport != 1900 and packet[UDP].dport != 1900:
        return None
    sender = _sender(packet)
    text = bytes(packet[UDP].payload).decode("utf-8", "replace")
    if sender is None or not (text.startswith("NOTIFY ") or text.startswith("HTTP/1.1 200")):
        return None
    server = None
    for line in text.split("\r\n")[1:]:
        key, _, value = line.partition(":")
        if key.strip().upper() == "SERVER":
            server = _text(value)
            break
    return Observation(sender[0], sender[1], "ssdp", server=server) if server else None


def observe(packet: Any) -> Observation | None:
    return from_dhcp(packet) or from_mdns(packet) or from_netbios(packet) or from_ssdp(packet) or from_arp(packet)
