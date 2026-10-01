from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Access, Device, Event, Service

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)


def test_mute_and_unmute_a_risky_service(client, db):
    device = Device(mac="00:00:5E:00:53:50", name="NAS", hostname="nas", access=Access.authorized)
    db.add(device)
    db.add(Service(mac=device.mac, port=21, proto="tcp", state="open", service="ftp", risk="high",
                   risk_reason="FTP sends passwords in clear text", first_seen=NOW, last_seen=NOW))
    db.flush()
    response = client.patch(f"/api/devices/{device.id}/services/21/tcp", json={"muted": True})
    assert response.json() == {"port": 21, "proto": "tcp", "muted": True}
    [listed] = client.get(f"/api/devices/{device.id}/services").json()
    assert listed["muted"] is True
    client.patch(f"/api/devices/{device.id}/services/21/tcp", json={"muted": True})
    client.patch(f"/api/devices/{device.id}/services/21/tcp", json={"muted": False})
    types = [e.type for e in db.scalars(select(Event).where(Event.mac == device.mac).order_by(Event.id))]
    assert types == ["security.risk_muted", "security.risk_unmuted"]
    assert client.patch(f"/api/devices/{device.id}/services/22/tcp", json={"muted": True}).status_code == 404
