"""Локальные метаданные проводок, которых нет в схеме ERPNext Journal Entry.

ERPNext хранит `posting_date` (дата возникновения транзакции — управляется
пользователем) и `creation` (таймстамп создания записи — авто). Но у Journal
Entry нет поля ВРЕМЕНИ возникновения. Дэн хочет указывать дату И время, когда
транзакция реально произошла, отдельно от момента внесения записи.

Поэтому время возникновения (полный ISO-datetime) держим здесь, ключ — имя
проводки (voucher PK в ERPNext). Дата всё равно дублируется в posting_date,
чтобы балансы/отчёты/фильтры ERPNext работали нативно; здесь — точное время.
"""

import sqlite3
from datetime import datetime

from counta.core.db import DB_PATH

# Мультиюзер: метаданные проводок у каждого тенанта свои.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS entry_meta (
    tenant INTEGER NOT NULL DEFAULT 1,
    voucher TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    PRIMARY KEY (tenant, voucher)
);
CREATE TABLE IF NOT EXISTS slept_entries (
    tenant INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    debit   TEXT NOT NULL,
    credit  TEXT NOT NULL,
    amount  REAL NOT NULL,
    posting_date TEXT NOT NULL,
    remark  TEXT,
    occurred_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_slept_account ON slept_entries(tenant, account);
"""


def _tid() -> int:
    from counta.core import tenant
    return tenant.require_current()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    for tbl in ("entry_meta", "slept_entries"):
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({tbl})")}
        if "tenant" not in cols:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
    return con


def set_occurred(voucher: str, occurred_at: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO entry_meta (tenant, voucher, occurred_at) VALUES (?,?,?) "
            "ON CONFLICT(tenant, voucher) DO UPDATE SET occurred_at=excluded.occurred_at",
            (_tid(), voucher, occurred_at))


def occurred_map(vouchers: list[str]) -> dict[str, str]:
    if not vouchers:
        return {}
    ph = ",".join("?" * len(vouchers))
    with _conn() as con:
        rows = con.execute(
            f"SELECT voucher, occurred_at FROM entry_meta WHERE tenant=? AND voucher IN ({ph})",
            (_tid(), *vouchers)).fetchall()
    return {r[0]: r[1] for r in rows}


def sleep_record(account: str, snap: dict, occurred_at: str | None) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO slept_entries (tenant, account, debit, credit, amount, posting_date, remark, occurred_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (_tid(), account, snap["debit"], snap["credit"], snap["amount"],
             snap["posting_date"], snap.get("remark", ""), occurred_at))


def sleeping_for(account: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT debit, credit, amount, posting_date, remark, occurred_at "
            "FROM slept_entries WHERE tenant=? AND account=?", (_tid(), account)).fetchall()
    return [{"debit": r[0], "credit": r[1], "amount": r[2], "posting_date": r[3],
             "remark": r[4], "occurred_at": r[5]} for r in rows]


def clear_sleeping(account: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM slept_entries WHERE tenant=? AND account=?", (_tid(), account))


def forget(voucher: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM entry_meta WHERE tenant=? AND voucher=?", (_tid(), voucher))


def parse_occurred(value: str | None) -> datetime | None:
    """Распарсить ISO-datetime из формы; None если пусто/некорректно.

    Принимаем форматы `datetime-local` (YYYY-MM-DDTHH:MM[:SS]) и полный ISO."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
