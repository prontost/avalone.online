"""Raw-data access for the double-entry finance ledger.

All SQL lives here. Every public operation receives ``tenant_id`` explicitly;
no context-variable access is performed inside the repository.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from avalone_finance.core import db


_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_led_accounts (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    account_name TEXT NOT NULL,
    root_type    TEXT NOT NULL,
    account_type TEXT DEFAULT '',
    is_group     INTEGER DEFAULT 0,
    disabled     INTEGER DEFAULT 0,
    PRIMARY KEY (tenant, name)
);
CREATE TABLE IF NOT EXISTS money_led_entries (
    tenant       INTEGER NOT NULL DEFAULT 1,
    name         TEXT NOT NULL,
    posting_date TEXT NOT NULL,
    user_remark  TEXT DEFAULT '',
    total_debit  REAL NOT NULL DEFAULT 0,
    docstatus    INTEGER NOT NULL DEFAULT 1,
    creation     TEXT NOT NULL,
    PRIMARY KEY (tenant, name)
);
CREATE TABLE IF NOT EXISTS money_led_lines (
    tenant  INTEGER NOT NULL DEFAULT 1,
    entry   TEXT NOT NULL,
    account TEXT NOT NULL,
    debit   REAL NOT NULL DEFAULT 0,
    credit  REAL NOT NULL DEFAULT 0,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);
CREATE INDEX IF NOT EXISTS idx_money_led_lines_entry   ON money_led_lines(tenant, entry);
CREATE INDEX IF NOT EXISTS idx_money_led_lines_account ON money_led_lines(tenant, account);
CREATE INDEX IF NOT EXISTS idx_money_led_entries_status ON money_led_entries(tenant, docstatus, posting_date);
CREATE TABLE IF NOT EXISTS money_led_seq (tenant INTEGER NOT NULL, year TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (tenant, year));
"""


class LedgerRepositoryError(Exception):
    """Internal repository failure; the service layer translates these into
    user-facing :class:`LedgerError` exceptions."""
    pass


class AccountInUseError(LedgerRepositoryError):
    def __init__(self, used: int) -> None:
        self.used = used


class UnbalancedEntriesError(LedgerRepositoryError):
    def __init__(self, bad: list[tuple]) -> None:
        self.bad = bad


class GlobalImbalanceError(LedgerRepositoryError):
    def __init__(self, debit: float, credit: float) -> None:
        self.debit = debit
        self.credit = credit


class LedgerRepository:
    """All raw SQL for the finance ledger."""

    def _conn(self) -> sqlite3.Connection:
        db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db.DB_PATH)
        con.execute("PRAGMA foreign_keys=OFF")  # composite keys are cleaned manually
        con.executescript(_SCHEMA)
        # migration of old single-tenant tables: add tenant column if missing
        for tbl in ("money_led_accounts", "money_led_entries", "money_led_lines", "money_led_seq"):
            try:
                cols = {r[1] for r in con.execute(f"PRAGMA table_info({tbl})")}
                if "tenant" not in cols:
                    con.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass
        return con

    def _next_voucher(self, con: sqlite3.Connection, tenant_id: int) -> str:
        year = str(datetime.now().year)
        row = con.execute(
            "SELECT n FROM money_led_seq WHERE tenant=? AND year=?", (tenant_id, year)
        ).fetchone()
        n = (row[0] if row else 0) + 1
        prefix = f"JE-{year}-"
        # collision guard for migrated entries
        while con.execute(
            "SELECT 1 FROM money_led_entries WHERE tenant=? AND name=?",
            (tenant_id, f"{prefix}{n:05d}"),
        ).fetchone():
            n += 1
        con.execute(
            "INSERT INTO money_led_seq (tenant, year, n) VALUES (?,?,?) "
            "ON CONFLICT(tenant, year) DO UPDATE SET n=excluded.n",
            (tenant_id, year, n),
        )
        return f"{prefix}{n:05d}"

    # ----------------------------------------------------------------- accounts
    def list_accounts(
        self,
        tenant_id: int,
        *,
        leaf_only: bool = True,
        include_disabled: bool = False,
    ) -> list[dict]:
        q = (
            "SELECT name, account_name, root_type, account_type, is_group, disabled "
            "FROM money_led_accounts WHERE tenant=?"
        )
        if leaf_only:
            q += " AND is_group=0"
        if not include_disabled:
            q += " AND disabled=0"
        with self._conn() as con:
            rows = con.execute(q, (tenant_id,)).fetchall()
        return [
            {
                "name": r[0],
                "account_name": r[1],
                "root_type": r[2],
                "account_type": r[3],
                "is_group": r[4],
                "disabled": r[5],
            }
            for r in rows
        ]

    def create_account_id(
        self,
        tenant_id: int,
        account_id: str,
        account_name: str,
        root_type: str,
        account_type: str = "",
    ) -> str:
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_led_accounts (tenant, name, account_name, root_type, account_type, is_group, disabled) "
                "VALUES (?,?,?,?,?,0,0) ON CONFLICT(tenant, name) DO NOTHING",
                (tenant_id, account_id, account_name, root_type, account_type),
            )
        return account_id

    def upsert_account(
        self,
        tenant_id: int,
        name: str,
        account_name: str,
        root_type: str,
        account_type: str = "",
        is_group: int = 0,
        disabled: int = 0,
    ) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_led_accounts (tenant, name, account_name, root_type, account_type, is_group, disabled) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant, name) DO UPDATE SET "
                "account_name=excluded.account_name, root_type=excluded.root_type, "
                "account_type=excluded.account_type, is_group=excluded.is_group, "
                "disabled=excluded.disabled",
                (tenant_id, name, account_name, root_type, account_type, is_group, disabled),
            )

    def disable_account(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_led_accounts SET disabled=1 WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    def enable_account(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_led_accounts SET disabled=0 WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    def delete_account(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            used = con.execute(
                "SELECT COUNT(*) FROM money_led_lines WHERE tenant=? AND account=?",
                (tenant_id, name),
            ).fetchone()[0]
            if used:
                raise AccountInUseError(used)
            con.execute(
                "DELETE FROM money_led_accounts WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    # ----------------------------------------------------------------- journal entries
    def post_journal_entry(
        self,
        tenant_id: int,
        entry_date: date,
        remark: str,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
        *,
        name: str | None = None,
        creation: str | None = None,
    ) -> str:
        amt = round(float(amount), 2)
        now = creation or datetime.now().isoformat(timespec="seconds")
        with self._conn() as con:
            nm = name or self._next_voucher(con, tenant_id)
            con.execute(
                "INSERT INTO money_led_entries (tenant, name, posting_date, user_remark, total_debit, docstatus, creation) "
                "VALUES (?,?,?,?,?,1,?)",
                (tenant_id, nm, entry_date.isoformat(), remark, amt, now),
            )
            con.execute(
                "INSERT INTO money_led_lines (tenant, entry, account, debit, credit) VALUES (?,?,?,?,0)",
                (tenant_id, nm, debit_account, amt),
            )
            con.execute(
                "INSERT INTO money_led_lines (tenant, entry, account, debit, credit) VALUES (?,?,?,0,?)",
                (tenant_id, nm, credit_account, amt),
            )
        return nm

    def cancel_journal_entry(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_led_entries SET docstatus=2 WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    def restore_cancelled(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_led_entries SET docstatus=1 WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    def set_status(self, tenant_id: int, name: str, docstatus: int) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE money_led_entries SET docstatus=? WHERE tenant=? AND name=?",
                (docstatus, tenant_id, name),
            )

    def delete_entry(self, tenant_id: int, name: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM money_led_lines WHERE tenant=? AND entry=?",
                (tenant_id, name),
            )
            con.execute(
                "DELETE FROM money_led_entries WHERE tenant=? AND name=?",
                (tenant_id, name),
            )

    def entry_accounts(self, tenant_id: int, name: str) -> tuple[str, str] | None:
        with self._conn() as con:
            rows = con.execute(
                "SELECT account, debit, credit FROM money_led_lines WHERE tenant=? AND entry=?",
                (tenant_id, name),
            ).fetchall()
        debit = next((r[0] for r in rows if r[1]), None)
        credit = next((r[0] for r in rows if r[2]), None)
        return (debit, credit) if debit and credit else None

    def entry_detail(self, tenant_id: int, name: str) -> dict | None:
        with self._conn() as con:
            e = con.execute(
                "SELECT posting_date, user_remark FROM money_led_entries WHERE tenant=? AND name=?",
                (tenant_id, name),
            ).fetchone()
            if not e:
                return None
            rows = con.execute(
                "SELECT account, debit, credit FROM money_led_lines WHERE tenant=? AND entry=?",
                (tenant_id, name),
            ).fetchall()
        debit = next((r[0] for r in rows if r[1]), None)
        credit = next((r[0] for r in rows if r[2]), None)
        amount = next((r[1] for r in rows if r[1]), 0)
        if not (debit and credit):
            return None
        return {
            "debit": debit,
            "credit": credit,
            "amount": float(amount),
            "posting_date": e[0],
            "remark": e[1] or "",
        }

    def entries_of_account(
        self,
        tenant_id: int,
        account: str,
        docstatus: tuple[int, ...] = (1,),
    ) -> list[str]:
        ph = ",".join("?" * len(docstatus))
        with self._conn() as con:
            rows = con.execute(
                f"SELECT DISTINCT l.entry FROM money_led_lines l "
                f"JOIN money_led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
                f"WHERE l.tenant=? AND l.account=? AND e.docstatus IN ({ph})",
                (tenant_id, account, *docstatus),
            ).fetchall()
        return [r[0] for r in rows]

    def entry_counts(self, tenant_id: int, account_names: list[str]) -> dict[str, int]:
        if not account_names:
            return {}
        ph = ",".join("?" * len(account_names))
        with self._conn() as con:
            rows = con.execute(
                f"SELECT l.account, COUNT(DISTINCT l.entry) FROM money_led_lines l "
                f"JOIN money_led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
                f"WHERE l.tenant=? AND l.account IN ({ph}) AND e.docstatus=1 GROUP BY l.account",
                (tenant_id, *account_names),
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def account_balance(
        self,
        tenant_id: int,
        account: str,
        on_date: date | None = None,
    ) -> Decimal:
        q = (
            "SELECT COALESCE(SUM(l.debit-l.credit),0) FROM money_led_lines l "
            "JOIN money_led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
            "WHERE l.tenant=? AND l.account=? AND e.docstatus=1"
        )
        params: list[Any] = [tenant_id, account]
        if on_date:
            q += " AND e.posting_date<=?"
            params.append(on_date.isoformat())
        with self._conn() as con:
            v = con.execute(q, params).fetchone()[0]
        return Decimal(str(v or 0))

    def recent_entries(
        self,
        tenant_id: int,
        limit: int = 10,
        *,
        extra_filters: list | None = None,
        order_by: str = "posting_date desc, name desc",
        docstatus: tuple[int, ...] = (1,),
    ) -> list[dict]:
        ph = ",".join("?" * len(docstatus))
        where = ["tenant=?", f"docstatus IN ({ph})"]
        params: list[Any] = [tenant_id, *docstatus]
        for f in extra_filters or []:
            field, op, val = f[0], f[1], f[2]
            col = {"posting_date": "posting_date", "creation": "creation", "total_debit": "total_debit"}.get(field)
            if not col or op not in (">=", "<=", ">", "<", "=", "!="):
                continue
            where.append(f"{col} {op} ?")
            params.append(val)
        safe_order = (
            order_by
            if all(c.isalnum() or c in " ,_" for c in order_by)
            else "posting_date desc"
        )
        q = (
            "SELECT name, posting_date, user_remark, total_debit, creation, docstatus "
            f"FROM money_led_entries WHERE {' AND '.join(where)} ORDER BY {safe_order} LIMIT ?"
        )
        params.append(limit)
        with self._conn() as con:
            rows = con.execute(q, params).fetchall()
        return [
            {
                "name": r[0],
                "posting_date": r[1],
                "user_remark": r[2],
                "total_debit": r[3],
                "creation": r[4],
                "docstatus": r[5],
            }
            for r in rows
        ]

    # ----------------------------------------------------------------- integrity
    def assert_balanced(self, tenant_id: int | None) -> int:
        with self._conn() as con:
            base = "FROM money_led_lines"
            params: list[Any] = []
            if tenant_id is not None:
                base += " WHERE tenant=?"
                params = [tenant_id]
            bad = con.execute(
                f"SELECT entry, SUM(debit), SUM(credit) {base} GROUP BY entry "
                "HAVING ROUND(SUM(debit),2)<>ROUND(SUM(credit),2)",
                params,
            ).fetchall()
            if bad:
                raise UnbalancedEntriesError(bad)
            gd, gc = con.execute(
                f"SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) {base}",
                params,
            ).fetchone()
            n = con.execute(
                "SELECT COUNT(*) FROM money_led_entries"
                + (" WHERE tenant=?" if tenant_id is not None else ""),
                params,
            ).fetchone()[0]
        if round(gd, 2) != round(gc, 2):
            raise GlobalImbalanceError(gd, gc)
        return n
