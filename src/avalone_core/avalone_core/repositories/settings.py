"""Runtime server settings repository."""

from __future__ import annotations

import sqlite3
from typing import Any

from avalone_core.database import Database, Repository


class SettingsRepository(Repository):
    """SQL access for the `avalone_global_settings` key/value table."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database.shared())

    def _conn(self) -> sqlite3.Connection:
        return self._db.connection()

    def get(self, key: str, default: str = "") -> str:
        with self._conn() as con:
            row = con.execute(
                "SELECT value FROM avalone_global_settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def get_many(self, keys: set[str]) -> dict[str, str]:
        if not keys:
            return {}
        placeholders = ",".join("?" * len(keys))
        with self._conn() as con:
            rows = con.execute(
                f"SELECT key, value FROM avalone_global_settings WHERE key IN ({placeholders})",
                tuple(keys),
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set(self, key: str, value: str) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO avalone_global_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            con.commit()

    def set_many(self, values: dict[str, str]) -> None:
        with self._conn() as con:
            for key, value in values.items():
                con.execute(
                    "INSERT INTO avalone_global_settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            con.commit()

    def all(self) -> dict[str, str]:
        with self._conn() as con:
            rows = con.execute("SELECT key, value FROM avalone_global_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def get_prefix(self, prefix: str) -> dict[str, str]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT key, value FROM avalone_global_settings WHERE key LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def migrate_from_legacy(
        self,
        keys: tuple[str, ...],
        source_table: str = "money_global_settings",
    ) -> None:
        """Copy missing settings from a legacy module table into the unified store."""
        with self._conn() as con:
            existing = {
                r["key"] for r in con.execute("SELECT key FROM avalone_global_settings").fetchall()
            }
            table_exists = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (source_table,)
            ).fetchone()
            if not table_exists:
                return
            for key in keys:
                if key in existing:
                    continue
                row = con.execute(
                    f"SELECT value FROM {source_table} WHERE key=?", (key,)
                ).fetchone()
                if row and row["value"]:
                    con.execute(
                        "INSERT INTO avalone_global_settings (key, value) VALUES (?, ?)",
                        (key, row["value"]),
                    )
                    existing.add(key)
            con.commit()
