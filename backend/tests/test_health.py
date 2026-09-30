def test_health_is_public_and_ok(bare_client):
    response = bare_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
