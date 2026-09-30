import pytest
from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether

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
