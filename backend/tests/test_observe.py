import pytest
from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS, DNSQR, DNSRR
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether
from scapy.packet import Raw

from app.sentinel.observe import Observation, observe

MAC = "00:00:5E:00:53:40"


def wire(packet):
    return Ether(bytes(packet))


def dhcp(message_type: str, op: int = 1, **options):
    opts = [("message-type", message_type), *options.items(), "end"]
    return wire(
        Ether(src=MAC.lower(), dst="ff:ff:ff:ff:ff:ff")
        / IP(src="0.0.0.0", dst="255.255.255.255")
        / UDP(sport=68, dport=67)
        / BOOTP(op=op, chaddr=bytes.fromhex(MAC.replace(":", "")))
        / DHCP(options=opts)
    )


def test_arp_reply():
    packet = wire(Ether(src=MAC.lower()) / ARP(op=2, hwsrc=MAC.lower(), psrc="192.168.1.40", pdst="192.168.1.220"))
    assert observe(packet) == Observation(MAC, "192.168.1.40", "arp")


def test_arp_probe_has_no_ip():
    packet = wire(Ether(src=MAC.lower()) / ARP(op=1, hwsrc=MAC.lower(), psrc="0.0.0.0", pdst="192.168.1.40"))
    assert observe(packet) == Observation(MAC, None, "arp")


def test_dhcp_request_carries_identity():
    packet = dhcp("request", requested_addr="192.168.1.50", hostname=b"pixel-7",
                  vendor_class_id=b"android-dhcp-14", param_req_list=[1, 3, 6, 15])
    obs = observe(packet)
    assert obs == Observation(MAC, "192.168.1.50", "dhcp", "pixel-7", "android-dhcp-14", (1, 3, 6, 15))
    assert obs.payload() == {"hostname": "pixel-7", "vendor_class": "android-dhcp-14", "param_list": [1, 3, 6, 15]}


def test_dhcp_discover_without_options():
    assert observe(dhcp("discover")) == Observation(MAC, None, "dhcp")


def test_garbage_hostname_is_decoded_safely():
    obs = observe(dhcp("request", hostname=b"\xff\xfebad\x00"))
    assert obs.hostname == "��bad"


@pytest.mark.parametrize(
    "packet",
    [
        pytest.param(dhcp("offer", op=2), id="server-offer"),
        pytest.param(wire(Ether() / IP(dst="192.168.1.1") / TCP(dport=443)), id="tcp"),
        pytest.param(wire(Ether(src=MAC.lower()) / ARP(op=3, hwsrc=MAC.lower(), psrc="192.168.1.40")), id="rarp"),
    ],
)
def test_ignored_packets(packet):
    assert observe(packet) is None


def test_dhcp_requested_zero_address_is_ignored():
    assert observe(dhcp("request", requested_addr="0.0.0.0")).ip is None


def _mdns(qr: int, records=None, questions=None):
    return wire(
        Ether(src=MAC.lower())
        / IP(src="192.168.1.40", dst="224.0.0.251")
        / UDP(sport=5353, dport=5353)
        / DNS(qr=qr, aa=qr, qd=questions or [], an=records or [])
    )


def test_mdns_announcement():
    packet = _mdns(1, [
        DNSRR(rrname="_googlecast._tcp.local.", type="PTR", rdata="Living-TV._googlecast._tcp.local."),
        DNSRR(rrname="living-tv.local.", type="A", rdata="192.168.1.40"),
        DNSRR(rrname="Living-TV._googlecast._tcp.local.", type="TXT", rdata=[b"md=Chromecast", b"fn=Living TV"]),
    ])
    obs = observe(packet)
    assert (obs.source, obs.ip, obs.hostname, obs.services, obs.model) == (
        "mdns", "192.168.1.40", "living-tv", ("_googlecast._tcp",), "Chromecast")
    assert obs.payload() == {"hostname": "living-tv", "services": ["_googlecast._tcp"], "model": "Chromecast"}


def test_mdns_query_is_ignored():
    assert observe(_mdns(0, questions=[DNSQR(qname="_googlecast._tcp.local.", qtype="PTR")])) is None


def _netbios_registration(name: str, suffix: str = "\x00", group: bool = False) -> bytes:
    padded = name.upper().ljust(15)[:15] + suffix
    encoded = "".join(chr(65 + (ord(c) >> 4)) + chr(65 + (ord(c) & 0x0F)) for c in padded)
    header = bytes([0x12, 0x34, 0x29, 0x10, 0, 1, 0, 0, 0, 0, 0, 1])
    question = bytes([0x20]) + encoded.encode() + b"\x00" + bytes([0, 0x20, 0, 1])
    flags = bytes([0x80 if group else 0x00, 0x00])
    additional = bytes([0xC0, 0x0C, 0, 0x20, 0, 1, 0, 0, 0x0E, 0x10, 0, 6]) + flags + bytes([192, 168, 1, 40])
    return header + question + additional


def test_netbios_registration():
    packet = wire(Ether(src=MAC.lower()) / IP(src="192.168.1.40", dst="192.168.1.255")
                  / UDP(sport=137, dport=137) / Raw(_netbios_registration("desktop-a")))
    assert observe(packet) == Observation(MAC, "192.168.1.40", "netbios", "DESKTOP-A")


def test_ssdp_notify_server_header():
    body = (b"NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nNT: upnp:rootdevice\r\n"
            b"SERVER: Linux/4.9 UPnP/1.0 Sample-TV/1.0\r\nNTS: ssdp:alive\r\n\r\n")
    packet = wire(Ether(src=MAC.lower()) / IP(src="192.168.1.40", dst="239.255.255.250")
                  / UDP(sport=1900, dport=1900) / Raw(body))
    obs = observe(packet)
    assert (obs.source, obs.server) == ("ssdp", "Linux/4.9 UPnP/1.0 Sample-TV/1.0")


def test_ssdp_search_request_is_ignored():
    body = b"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nST: ssdp:all\r\n\r\n"
    packet = wire(Ether(src=MAC.lower()) / IP(src="192.168.1.40", dst="239.255.255.250")
                  / UDP(sport=50000, dport=1900) / Raw(body))
    assert observe(packet) is None


@pytest.mark.parametrize(("name", "suffix", "group"), [("WORKGROUP", "\x00", True), ("WORKGROUP", "\x1e", False),
                                                      ("DESKTOP-A", "\x1d", False)])
def test_netbios_group_and_service_names_are_ignored(name, suffix, group):
    packet = wire(Ether(src=MAC.lower()) / IP(src="192.168.1.40", dst="192.168.1.255")
                  / UDP(sport=137, dport=137) / Raw(_netbios_registration(name, suffix, group)))
    assert observe(packet) is None


def test_sleep_proxy_answers_for_other_hosts_are_ignored():
    packet = _mdns(1, [
        DNSRR(rrname="_smb._tcp.local.", type="PTR", rdata="Office-Mac._smb._tcp.local."),
        DNSRR(rrname="office-mac.local.", type="A", rdata="192.168.1.77"),
    ])
    assert observe(packet) is None


def test_hostname_comes_from_the_senders_own_address():
    packet = _mdns(1, [
        DNSRR(rrname="living-tv.local.", type="A", rdata="192.168.1.40"),
        DNSRR(rrname="other.local.", type="A", rdata="192.168.1.77"),
    ])
    assert observe(packet).hostname == "living-tv"


def test_capture_filter_drops_mdns_queries_in_the_kernel():
    from app.sentinel.main import FILTER

    assert "udp[10] & 0x80 != 0" in FILTER and "port 5353" in FILTER
