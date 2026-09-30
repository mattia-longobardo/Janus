from sqlalchemy import select

from app.models import Event, NotificationRule
from app.notify.store import default_rule_rows


def _seed(db):
    db.add_all([NotificationRule(**row) for row in default_rule_rows()])
    db.flush()


def test_get_returns_settings_and_rules(client, db):
    _seed(db)
    body = client.get("/api/notifications").json()
    assert body["settings"]["quiet_start"] == "23:00" and body["settings"]["enabled"] is True
    new = next(r for r in body["rules"] if r["event_type"] == "device.new")
    assert new == {"event_type": "device.new", "label": "New device waiting for approval", "email": True, "gotify": True}
    assert all(r["event_type"] != "notify.test" for r in body["rules"])


def test_put_settings_validates(client, db):
    ok = client.put("/api/notifications/settings", json={
        "enabled": True, "quiet_start": "22:30", "quiet_end": "06:45", "email_enabled": True,
        "email_recipient": "owner@example.org", "gotify_enabled": False})
    assert ok.status_code == 200 and client.get("/api/notifications").json()["settings"]["gotify_enabled"] is False
    bad_time = client.put("/api/notifications/settings", json={
        "enabled": True, "quiet_start": "25:00", "quiet_end": None, "email_enabled": True,
        "email_recipient": "", "gotify_enabled": True})
    assert bad_time.status_code == 422
    bad_mail = client.put("/api/notifications/settings", json={
        "enabled": True, "quiet_start": None, "quiet_end": None, "email_enabled": True,
        "email_recipient": "not-an-email", "gotify_enabled": True})
    assert bad_mail.status_code == 422


def test_put_rules(client, db):
    _seed(db)
    response = client.put("/api/notifications/rules", json=[{"event_type": "device.offline", "email": True, "gotify": False}])
    assert response.status_code == 200
    offline = next(r for r in client.get("/api/notifications").json()["rules"] if r["event_type"] == "device.offline")
    assert (offline["email"], offline["gotify"]) == (True, False)
    assert client.put("/api/notifications/rules", json=[{"event_type": "nope", "email": True, "gotify": True}]).status_code == 422


def test_test_notification_is_queued(client, db):
    assert client.post("/api/notifications/test/gotify").status_code == 202
    event = db.scalar(select(Event).where(Event.type == "notify.test"))
    assert event.payload == {"channel": "gotify"}
    assert client.post("/api/notifications/test/sms").status_code == 404
