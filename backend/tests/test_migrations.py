from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

from app import models  # noqa: F401
from app.db import Base
from tests.conftest import TEST_DATABASE_URL


def test_migrations_match_models():
    eng = create_engine(TEST_DATABASE_URL, connect_args={"options": "-csearch_path=migcheck"})
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS migcheck CASCADE"))
        conn.execute(text("CREATE SCHEMA migcheck"))
    try:
        with eng.begin() as conn:
            cfg = Config("alembic.ini")
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        with eng.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diffs == []
    finally:
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS migcheck CASCADE"))
        eng.dispose()
