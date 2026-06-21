"""Global (instance-wide) settings stored in SQLite.

Per-tenant settings live in notify.user_settings. These settings affect the
whole instance and are writable by the owner (tenant_id == OWNER_TENANT_ID).
"""
import sqlite3

from counta.core.db import DB_PATH
from counta.core import tenant

_SCHEMA = """
CREATE TABLE IF NOT EXISTS global_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Дефолты перекрываются env при чтении через config.py, но здесь — фолбэк
# для runtime, когда в БД ещё ничего не записано.
DEFAULTS = {
    "registration_mode": "open",
    "registration_invite_code": "",
    "strict_password_policy": "false",
    "default_currency": "KRW",
    "web_base_url": "https://counta.avalone.online",
}


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    return con


def get(key: str) -> str | None:
    """Return stored value or None if the key has never been set in DB."""
    with _conn() as con:
        r = con.execute("SELECT value FROM global_settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else None


def set(key: str, value: str) -> None:
    """Only instance admins are allowed to change global settings."""
    if not tenant.is_admin(tenant.current()):
        raise PermissionError("only admins can change global settings")
    with _conn() as con:
        con.execute(
            "INSERT INTO global_settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def get_all() -> dict:
    with _conn() as con:
        rows = dict(con.execute("SELECT key, value FROM global_settings").fetchall())
    return {**DEFAULTS, **rows}
