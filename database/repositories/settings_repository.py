"""Repository for app_settings."""

from ..db import Database
from core.exceptions import DatabaseError


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str) -> str | None:
        row = self.db.fetchone("SELECT value FROM app_settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        self.db.set_setting(key, value)

    def get_all(self) -> dict:
        return self.db.get_all_settings()
