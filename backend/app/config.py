from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JANUS_", extra="ignore")

    database_url: str = "postgresql+psycopg://janus:janus@localhost:5432/janus"
    internal_token: str = ""
    pihole_url: str = "http://192.168.1.220:1000"
    pihole_password: str = ""
    subnet: str = "192.168.1.0/24"
    gateway: str = "192.168.1.1"
    quarantine_start: str = "192.168.1.240"
    quarantine_end: str = "192.168.1.254"
    reservation_lease: str = "24h"
    sync_mode: Literal["dry-run", "apply"] = "dry-run"
    reconcile_interval_s: int = 300
    heartbeat_path: str = "/tmp/janus-worker.heartbeat"
    timezone: str = "Europe/Rome"


settings = Settings()
