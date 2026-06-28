"""Raw SQL storage for the money account registry.

All operations require an explicit ``tenant_id``. Schema creation and
migrations (currency / label / tenant columns) happen on every connection.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from avalone_finance.core import db as _db


class MoneyAccountRepository:
    """SQLite persistence for per-tenant money account metadata."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS money_money_accounts (
        tenant INTEGER NOT NULL DEFAULT 1,
        account TEXT NOT NULL,
        kind TEXT,
        ord INTEGER DEFAULT 0,
        currency TEXT DEFAULT 'KRW',
        label TEXT,
        PRIMARY KEY (tenant, account)
    );
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        """Open a connection, ensuring the schema and migrations are applied."""
        db_path = self._db_path or _db.DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path)
        con.executescript(self._SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(money_money_accounts)")}
        if "currency" not in cols:
            con.execute("ALTER TABLE money_money_accounts ADD COLUMN currency TEXT DEFAULT 'KRW'")
        if "label" not in cols:
            con.execute("ALTER TABLE money_money_accounts ADD COLUMN label TEXT")
        if "tenant" not in cols:
            con.execute("ALTER TABLE money_money_accounts ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
        return con

    def set_label(self, tenant_id: int, account: str, label: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_money_accounts SET label=? WHERE tenant=? AND account=?",
                (label, tenant_id, account),
            )

    def account_label(self, tenant_id: int, account: str) -> str | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT label FROM money_money_accounts WHERE tenant=? AND account=?",
                (tenant_id, account),
            ).fetchone()
        return row[0] if row else None

    def register(
        self,
        tenant_id: int,
        account: str,
        kind: str,
        ord: int,
        currency: str,
        *,
        update_currency: bool = True,
    ) -> None:
        update_clause = (
            "kind=excluded.kind, ord=excluded.ord"
            + (", currency=excluded.currency" if update_currency else "")
        )
        sql = (
            "INSERT INTO money_money_accounts (tenant, account, kind, ord, currency) "
            "VALUES (?,?,?,?,?) "
            f"ON CONFLICT(tenant, account) DO UPDATE SET {update_clause}"
        )
        with self._conn() as con:
            con.execute(sql, (tenant_id, account, kind, ord, currency))

    def set_currency(self, tenant_id: int, account: str, currency: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_money_accounts SET currency=? WHERE tenant=? AND account=?",
                (currency, tenant_id, account),
            )

    def unregister(self, tenant_id: int, account: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM money_money_accounts WHERE tenant=? AND account=?",
                (tenant_id, account),
            )

    def registered(self, tenant_id: int) -> dict[str, str]:
        """Return {account: kind} ordered by ``ord``, then account name."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT account, kind FROM money_money_accounts "
                "WHERE tenant=? ORDER BY ord, account",
                (tenant_id,),
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def registered_full(self, tenant_id: int) -> dict[str, dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT account, kind, ord, currency FROM money_money_accounts "
                "WHERE tenant=? ORDER BY ord, account",
                (tenant_id,),
            ).fetchall()
        return {r[0]: {"kind": r[1], "ord": r[2], "currency": r[3]} for r in rows}

    def account_currency(self, tenant_id: int, account: str) -> str | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT currency FROM money_money_accounts WHERE tenant=? AND account=?",
                (tenant_id, account),
            ).fetchone()
        return row[0] if row else None
