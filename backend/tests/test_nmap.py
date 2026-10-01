import pytest

from app.intel.nmap import PortResult, classify, parse_nmap_xml

XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sT -sV 192.168.1.40">
  <host>
    <status state="up"/>
    <address addr="192.168.1.40" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22"><state state="open"/><service name="ssh" product="OpenSSH" version="9.2p1" extrainfo="Debian 2"/></port>
      <port protocol="tcp" portid="23"><state state="open"/><service name="telnet"/></port>
      <port protocol="tcp" portid="80"><state state="filtered"/><service name="http"/></port>
      <port protocol="tcp" portid="8443"><state state="open"/></port>
    </ports>
  </host>
</nmaprun>"""


def test_parse_open_ports_only():
    assert parse_nmap_xml(XML) == [
        PortResult(22, "tcp", "ssh", "OpenSSH 9.2p1 Debian 2"),
        PortResult(23, "tcp", "telnet", None),
        PortResult(8443, "tcp", None, None),
    ]


def test_parse_host_down_timeout_and_malformed():
    with pytest.raises(ValueError, match="down"):
        parse_nmap_xml('<?xml version="1.0"?><nmaprun><host><status state="down"/></host></nmaprun>')
    with pytest.raises(ValueError, match="down"):
        parse_nmap_xml('<?xml version="1.0"?><nmaprun></nmaprun>')
    with pytest.raises(ValueError, match="timed out"):
        parse_nmap_xml('<?xml version="1.0"?><nmaprun><host timedout="true"><status state="up"/></host></nmaprun>')
    with pytest.raises(ValueError):
        parse_nmap_xml("<nmaprun><host>")


@pytest.mark.parametrize(
    ("port", "service", "risk"),
    [
        (23, "telnet", "high"),
        (2323, "telnet", "high"),
        (21, "ftp", "warning"),
        (5900, "vnc", "warning"),
        (445, "microsoft-ds", "none"),
        (139, "netbios-ssn", "none"),
        (5432, "postgresql", "warning"),
        (6379, None, "warning"),
        (5000, "upnp", "warning"),
        (22, "ssh", "none"),
        (443, "https", "none"),
    ],
)
def test_classify(port, service, risk):
    level, reason = classify(port, service)
    assert level == risk
    assert (reason is None) == (risk == "none")
