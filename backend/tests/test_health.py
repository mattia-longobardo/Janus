from datetime import UTC, datetime

from app.models import Access, Device, Service

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)


def _device(db, mac, name, ip, *, static=None, online=True):
    device = Device(mac=mac, name=name, hostname=name.lower(), access=Access.authorized, static_ip=static,
                    last_ip=ip, online=online)
    db.add(device)
    db.flush()
    return device


def test_health_flags_mismatch_conflicts_and_unmuted_risks(client, db):
    ok = _device(db, "00:00:5E:00:53:60", "OK_PC", "192.168.1.10", static="192.168.1.10")
    moved = _device(db, "00:00:5E:00:53:61", "MOVED", "192.168.1.30", static="192.168.1.11")
    twin = _device(db, "00:00:5E:00:53:62", "TWIN", "192.168.1.30", static="192.168.1.30")
    boot = _device(db, "00:00:5E:00:53:63", "BOOTING", "169.254.191.63", static="192.168.1.12")
    nas = _device(db, "00:00:5E:00:53:64", "NAS", "192.168.1.13", static="192.168.1.13")
    for port, risk, muted in ((21, "high", True), (1900, "warning", False)):
        db.add(Service(mac=nas.mac, port=port, proto="tcp", state="open", service="x", risk=risk, muted=muted,
                       first_seen=NOW, last_seen=NOW))
    db.flush()
    by_name = {d["name"]: d for d in client.get("/api/devices").json()}
    assert (by_name["OK_PC"]["health"], by_name["OK_PC"]["issues"]) == ("ok", [])
    assert by_name["MOVED"]["health"] == "critical"
    assert {i["kind"] for i in by_name["MOVED"]["issues"]} == {"ip_mismatch", "ip_conflict"}
    assert by_name["MOVED"]["issues"][0]["message"] == "Using 192.168.1.30 instead of its reserved address 192.168.1.11"
    assert [i["kind"] for i in by_name["TWIN"]["issues"]] == ["ip_conflict"]
    assert by_name["BOOTING"]["health"] == "ok"
    assert by_name["NAS"]["health"] == "warning"
    assert [i["message"] for i in by_name["NAS"]["issues"]] == ["Moderate risk on port 1900/tcp (x)"]
    assert client.get(f"/api/devices/{moved.id}").json()["health"] == "critical"
    assert ok and twin and boot
