WINDOW = {"name": "Router & modem daily reboot", "start_time": "05:00", "duration_min": 15, "days": 127,
          "enabled": True, "mute_alerts": True, "pause_isolation": True}


def test_crud(client):
    created = client.post("/api/maintenance-windows", json=WINDOW)
    assert created.status_code == 201
    wid = created.json()["id"]
    assert client.get("/api/maintenance-windows").json() == [{**WINDOW, "id": wid}]
    patched = client.patch(f"/api/maintenance-windows/{wid}", json={"start_time": "04:30", "duration_min": 30})
    assert (patched.json()["start_time"], patched.json()["duration_min"]) == ("04:30", 30)
    assert client.delete(f"/api/maintenance-windows/{wid}").status_code == 204
    assert client.get("/api/maintenance-windows").json() == []


def test_validation(client):
    assert client.post("/api/maintenance-windows", json={**WINDOW, "start_time": "5am"}).status_code == 422
    assert client.post("/api/maintenance-windows", json={**WINDOW, "days": 0}).status_code == 422
    assert client.post("/api/maintenance-windows", json={**WINDOW, "duration_min": 0}).status_code == 422
    assert client.patch("/api/maintenance-windows/999", json={"name": "x"}).status_code == 404
    wid = client.post("/api/maintenance-windows", json=WINDOW).json()["id"]
    assert client.patch(f"/api/maintenance-windows/{wid}", json={"name": None}).status_code == 422
