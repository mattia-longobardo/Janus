import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.config import settings
from app.db import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "JANUS_TEST_DATABASE_URL", "postgresql+psycopg://janus:janus@localhost:5432/janus_test"
)
TOKEN = "test-token"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def client(db, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "internal_token", TOKEN)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, headers={"X-Janus-Internal-Token": TOKEN}) as test_client:
        yield test_client
