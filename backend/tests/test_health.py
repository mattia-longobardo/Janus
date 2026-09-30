from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app


def test_health_is_public_and_ok(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_database_down():
    class Broken:
        def execute(self, *args, **kwargs):
            from sqlalchemy.exc import OperationalError
            raise OperationalError("SELECT 1", {}, Exception("down"))

    app = create_app()
    app.dependency_overrides[get_db] = lambda: Broken()
    assert TestClient(app).get("/api/health").status_code == 503
