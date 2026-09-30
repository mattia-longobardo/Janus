from collections.abc import Iterator
from contextlib import contextmanager
from datetime import time

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, create_engine, text

from app import models  # noqa: F401
from app.db import Base
from app.notify.store import default_rule_rows
from tests.conftest import TEST_DATABASE_URL


@contextmanager
def _migrated(schema: str) -> Iterator[Connection]:
    eng = create_engine(TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    try:
        with eng.begin() as conn:
            cfg = Config("alembic.ini")
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        with eng.connect() as conn:
            yield conn
    finally:
        with eng.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        eng.dispose()


def test_migrations_match_models():
    with _migrated("migcheck") as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_migration_seeds_default_window_and_rules():
    with _migrated("migseed") as conn:
        windows = conn.execute(text("SELECT name, start_time, duration_min, days, enabled, mute_alerts FROM maintenance_windows")).all()
        assert windows == [("Router & modem daily reboot", time(5, 0), 15, 127, True, True)]
        rules = conn.execute(text("SELECT event_type, channel, enabled FROM notification_rules ORDER BY event_type, channel")).all()
        expected = sorted((r["event_type"], r["channel"], r["enabled"]) for r in default_rule_rows())
        assert [tuple(r) for r in rules] == expected
