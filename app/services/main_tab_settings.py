import sqlite3
from contextlib import closing
from pathlib import Path


class MainTabSettingsService:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def get_main_tab_url(self, default_url: str) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = ?",
                ("main_tab_url",),
            ).fetchone()
        return row[0] if row else default_url

    def set_main_tab_url(self, url: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO app_settings(setting_key, setting_value)
                VALUES (?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
                """,
                ("main_tab_url", url),
            )
