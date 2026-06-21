"""User settings (SQLite) + outbound e-mail channel.

Push-уведомления и недельный итог удалены 2026-06-18 (нечего слать). Остались:
- user_settings (per-tenant): язык, раскладка главной, e-mail.
- _send_email: единственный исходящий канал — нужен для восстановления
  логина/пароля по почте и кодов подтверждения (security.py).
"""

import logging
import smtplib
import sqlite3
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from counta.core.db import DB_PATH
from counta.core.config import settings as cfg

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_settings (
    tenant INTEGER NOT NULL DEFAULT 1,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (tenant, key)
);
"""

DEFAULTS = {
    "email": "",
    "lang": "auto",         # auto | ru | en | ko; auto разрешается в браузере
    "theme": "auto",        # auto | light | dark
    # порядок и видимость виджетов главной: "widget:1" видим, ":0" скрыт
    "layout": "balances:1,journal:1",
}


def user_lang() -> str:
    return get_settings().get("lang", "ru")


def _tid() -> int:
    from counta.core import tenant
    return tenant.require_current()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(user_settings)")}
    if "tenant" not in cols:
        con.execute("ALTER TABLE user_settings ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
    return con


def get_settings() -> dict:
    with _conn() as con:
        rows = dict(con.execute("SELECT key, value FROM user_settings WHERE tenant=?",
                                (_tid(),)).fetchall())
    return {**DEFAULTS, **rows}


def set_settings(updates: dict) -> dict:
    allowed = set(DEFAULTS)
    tid = _tid()
    with _conn() as con:
        for k, v in updates.items():
            if k in allowed:
                con.execute(
                    "INSERT INTO user_settings (tenant, key, value) VALUES (?,?,?) "
                    "ON CONFLICT(tenant, key) DO UPDATE SET value=excluded.value",
                    (tid, k, str(v)))
    return get_settings()


def _send_email(to: str, title: str, body: str) -> bool:
    s = cfg()
    if not (s.smtp_host and s.smtp_user and s.smtp_password and to):
        return False
    from_addr = (s.smtp_from or s.smtp_user)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Counta · {title}"
    # Имя отправителя + корректные Date/Message-ID/Reply-To снижают шанс попасть в
    # спам (письма без них чаще режутся). From может отличаться от SMTP-логина.
    msg["From"] = formataddr(("Counta", from_addr))
    msg["To"] = to
    msg["Reply-To"] = from_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1])
    try:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("email send failed")
        return False
