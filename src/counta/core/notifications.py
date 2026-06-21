"""Журнал уведомлений пользователя в разрезе приложений.

Каждое уведомление привязано к пользователю (tenant_id) и к приложению (app).
Это позволяет вести отдельные журналы для Counta, Ride и будущих приложений
платформы avalone.online.
"""

import sqlite3
from datetime import datetime, timezone

from counta.core.db import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app          TEXT NOT NULL,
    kind         TEXT DEFAULT 'info',
    title        TEXT NOT NULL,
    body         TEXT DEFAULT '',
    read_at      TEXT DEFAULT '',
    dismissed_at TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notif_tenant_app ON notifications(tenant_id, app);
CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add(tenant_id: int, app: str, title: str, body: str = "", kind: str = "info") -> int:
    """Добавить уведомление. Возвращает id."""
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO notifications (tenant_id, app, kind, title, body, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, app, kind, title, body, _now()),
        )
        return cur.lastrowid or 0


def list_(
    tenant_id: int,
    app: str,
    filter: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Список уведомлений с пагинацией.

    filter:
      - all       — все неудалённые
      - unread    — непрочитанные
      - read      — прочитанные
      - dismissed — удалённые/скрытые
    """
    where = "tenant_id = ? AND app = ?"
    params: list = [tenant_id, app]

    if filter == "unread":
        where += " AND read_at = '' AND dismissed_at = ''"
    elif filter == "read":
        where += " AND read_at <> '' AND dismissed_at = ''"
    elif filter == "dismissed":
        where += " AND dismissed_at <> ''"
    else:  # all
        where += " AND dismissed_at = ''"

    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        total = con.execute(
            f"SELECT COUNT(*) FROM notifications WHERE {where}",
            params,
        ).fetchone()[0]

    entries = [dict(r) for r in rows]
    return {
        "entries": entries,
        "total": total,
        "has_more": offset + len(entries) < total,
    }


def mark_read(ids: list[int], tenant_id: int) -> int:
    """Пометить уведомления прочитанными. Возвращает число затронутых."""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with _conn() as con:
        cur = con.execute(
            f"UPDATE notifications SET read_at = ? WHERE tenant_id = ? AND id IN ({placeholders})",
            (_now(), tenant_id, *ids),
        )
        return cur.rowcount


def mark_dismissed(ids: list[int], tenant_id: int) -> int:
    """Скрыть/удалить уведомления. Возвращает число затронутых."""
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with _conn() as con:
        cur = con.execute(
            f"UPDATE notifications SET dismissed_at = ? WHERE tenant_id = ? AND id IN ({placeholders})",
            (_now(), tenant_id, *ids),
        )
        return cur.rowcount


def count_unread(tenant_id: int, app: str) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM notifications WHERE tenant_id = ? AND app = ? "
            "AND read_at = '' AND dismissed_at = ''",
            (tenant_id, app),
        ).fetchone()
    return row[0] if row else 0
