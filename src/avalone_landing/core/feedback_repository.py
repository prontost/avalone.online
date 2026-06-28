"""Feedback data access for the Avalone portal."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from avalone_core.database import Database, Repository


class FeedbackRepository(Repository):
    """SQL access for the `avalone_feedback` table."""

    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db or Database.shared())

    def _conn(self) -> sqlite3.Connection:
        return self._db.connection()

    def create(
        self,
        user_id: int | None,
        source_page: str,
        contact: str,
        message: str,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO avalone_feedback (user_id, source_page, contact, message, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, source_page, contact, message, created_at),
            )
            con.commit()
            return cur.lastrowid or 0

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT f.id, f.user_id, f.source_page, f.contact, f.message, f.created_at, "
                "u.login, u.email "
                "FROM avalone_feedback f "
                "LEFT JOIN users u ON u.id = f.user_id "
                "ORDER BY f.created_at DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "login": row["login"] or "",
                "email": row["email"] or "",
                "contact": row["contact"] or "",
                "source_page": row["source_page"] or "",
                "message": row["message"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
