from app.events import record_event


def test_event_log_filters_and_paginates(client, db):
    for i in range(5):
        record_event(db, "device.new", f"00:00:5E:00:53:4{i}", {"n": i})
    record_event(db, "sync.applied", None, {"added": []})
    newest = client.get("/api/events", params={"limit": 2}).json()
    assert [e["type"] for e in newest] == ["sync.applied", "device.new"]
    older = client.get("/api/events", params={"limit": 10, "before_id": newest[-1]["id"], "type": "device.new"}).json()
    assert [e["payload"]["n"] for e in older] == [3, 2, 1, 0]
    by_mac = client.get("/api/events", params={"mac": "00:00:5E:00:53:42"}).json()
    assert [e["payload"]["n"] for e in by_mac] == [2]
    assert client.get("/api/events", params={"limit": 0}).status_code == 422
