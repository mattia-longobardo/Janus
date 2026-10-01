def test_get_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert (body["timezone"], body["time_format"], body["sync_mode"]) == ("Europe/Rome", "24h", "dry-run")
    assert body["network"]["subnet"] == "192.168.1.0/24"
    assert body["network"]["quarantine_start"] == "192.168.1.240"
    assert body["scan_window"] == {"start": "08:00", "end": "22:00"}


def test_put_settings(client):
    body = client.put("/api/settings", json={"timezone": "Europe/London", "time_format": "12h"}).json()
    assert (body["timezone"], body["time_format"]) == ("Europe/London", "12h")
    assert client.get("/api/settings").json()["timezone"] == "Europe/London"


def test_put_settings_rejects_unknown_zone_and_format(client):
    assert client.put("/api/settings", json={"timezone": "Mars/Olympus"}).status_code == 422
    assert client.put("/api/settings", json={"time_format": "36h"}).status_code == 422
