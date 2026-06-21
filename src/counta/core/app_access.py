"""Управление доступом пользователей к приложениям платформы avalone.online.

Реестр приложений (KNOWN_APPS) живёт в коде: новое приложение добавляется
сюда, и админ может включить/выключить доступ конкретным пользователям.
По умолчанию публичные приложения (public=True) доступны всем; отключение
записывается в user_apps и скрывает приложение из переключателя.

Таблица user_apps ссылается на users с ON DELETE CASCADE, но из-за того, что
SQLite по умолчанию не включает foreign_keys, tenant.delete_user явно чистит
user_apps (и notifications) вместе с пользователем.
"""

import sqlite3
from datetime import datetime, timezone

from counta.core.db import DB_PATH

# Реестр приложений платформы. id — технический ключ, используется в URL/API.
KNOWN_APPS: dict[str, dict] = {
    "counta": {"id": "counta", "name": "Counta", "icon": "🏠", "public": True},
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_apps (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_id     TEXT NOT NULL,
    enabled    INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, app_id)
);
CREATE INDEX IF NOT EXISTS idx_user_apps_enabled ON user_apps(user_id, enabled);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def registry() -> list[dict]:
    """Публичный реестр всех приложений платформы (для UI)."""
    return [dict(meta) for meta in KNOWN_APPS.values()]


def _rows_for(user_id: int) -> dict[str, bool]:
    with _conn() as con:
        rows = con.execute(
            "SELECT app_id, enabled FROM user_apps WHERE user_id=?", (user_id,)
        ).fetchall()
    return {r["app_id"]: bool(r["enabled"]) for r in rows}


def list_for_user(user_id: int) -> list[str]:
    """Список app_id, доступных пользователю (для переключателя)."""
    explicit = _rows_for(user_id)
    return [
        app_id
        for app_id, meta in KNOWN_APPS.items()
        if explicit.get(app_id, meta.get("public", False))
    ]


def is_accessible(user_id: int, app_id: str) -> bool:
    meta = KNOWN_APPS.get(app_id)
    if not meta:
        return False
    explicit = _rows_for(user_id)
    return explicit.get(app_id, meta.get("public", False))


def list_for_admin(user_id: int) -> list[dict]:
    """Детальное состояние доступа для админки (все известные приложения)."""
    explicit = _rows_for(user_id)
    return [
        {
            "id": app_id,
            "name": meta["name"],
            "icon": meta.get("icon", ""),
            "enabled": explicit.get(app_id, meta.get("public", False)),
        }
        for app_id, meta in KNOWN_APPS.items()
    ]


def set_access(user_id: int, app_id: str, enabled: bool) -> None:
    """Включить/выключить доступ пользователя к приложению."""
    if app_id not in KNOWN_APPS:
        raise ValueError(f"unknown app: {app_id}")
    with _conn() as con:
        con.execute(
            """
            INSERT INTO user_apps (user_id, app_id, enabled, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, app_id) DO UPDATE SET enabled=excluded.enabled
            """,
            (user_id, app_id, 1 if enabled else 0, _now()),
        )


def grant_default(user_id: int) -> None:
    """При регистрации даём доступ ко всем публичным приложениям по умолчанию."""
    for app_id, meta in KNOWN_APPS.items():
        if meta.get("public"):
            set_access(user_id, app_id, True)


def delete_for_user(user_id: int) -> None:
    """Явно удалить все записи доступа пользователя (для tenant.delete_user)."""
    with _conn() as con:
        con.execute("DELETE FROM user_apps WHERE user_id=?", (user_id,))
