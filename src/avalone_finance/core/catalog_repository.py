"""Raw-data access for per-tenant category labels.

All SQL for ``money_catalog_i18n`` lives here. Every public operation receives
``tenant_id`` explicitly; no context-variable access is performed inside the
repository.
"""

from __future__ import annotations

import sqlite3

from avalone_finance.core import db


_SCHEMA = """
CREATE TABLE IF NOT EXISTS money_catalog_i18n (
    tenant INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    ru TEXT, en TEXT, ko TEXT,
    PRIMARY KEY (tenant, account)
);
"""


class CatalogRepository:
    """All raw SQL for the per-tenant category label table."""

    def _conn(self) -> sqlite3.Connection:
        db.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db.DB_PATH)
        con.executescript(_SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(money_catalog_i18n)")}
        if "tenant" not in cols:
            con.execute(
                "ALTER TABLE money_catalog_i18n ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1"
            )
        return con

    def set_labels(self, tenant_id: int, account: str, ru: str, en: str, ko: str) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO money_catalog_i18n (tenant, account, ru, en, ko) VALUES (?,?,?,?,?) "
                "ON CONFLICT(tenant, account) DO UPDATE SET ru=excluded.ru, en=excluded.en, ko=excluded.ko",
                (tenant_id, account, ru, en, ko),
            )

    def forget_labels(self, tenant_id: int, account: str) -> None:
        with self._conn() as con:
            con.execute(
                "DELETE FROM money_catalog_i18n WHERE tenant=? AND account=?",
                (tenant_id, account),
            )

    def user_labels(self, tenant_id: int) -> dict[str, dict]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT account, ru, en, ko FROM money_catalog_i18n WHERE tenant=?",
                (tenant_id,),
            ).fetchall()
        return {r[0]: {"ru": r[1], "en": r[2], "ko": r[3]} for r in rows}

    def known_accounts(self, tenant_id: int) -> set[str]:
        return set(self.user_labels(tenant_id))

    def is_user_category(self, tenant_id: int, account: str) -> bool:
        return account in self.known_accounts(tenant_id)
