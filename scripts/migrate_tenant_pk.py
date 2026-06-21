"""Одноразовая миграция: пересоздать таблицы с КОМПОЗИТНЫМ PK (tenant, ...).

ALTER TABLE ADD COLUMN добавил колонку tenant, но PRIMARY KEY в SQLite так не
меняется — остался одно-колоночный, из-за чего ON CONFLICT(tenant,name) падает.
Здесь: для каждой таблицы создаём *_new с правильным PK, копируем данные
(существующие → tenant=1), сваповываем. Бэкап перед запуском.

Запуск: .venv/bin/python scripts/migrate_tenant_pk.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path.home() / ".counta" / "counta.db"

# таблица -> (новый CREATE, список колонок в порядке для копирования)
REBUILDS = {
    "led_accounts": (
        """CREATE TABLE led_accounts_new (
            tenant INTEGER NOT NULL DEFAULT 1, name TEXT NOT NULL,
            account_name TEXT NOT NULL, root_type TEXT NOT NULL,
            account_type TEXT DEFAULT '', is_group INTEGER DEFAULT 0,
            disabled INTEGER DEFAULT 0, PRIMARY KEY (tenant, name))""",
        "tenant, name, account_name, root_type, account_type, is_group, disabled"),
    "led_entries": (
        """CREATE TABLE led_entries_new (
            tenant INTEGER NOT NULL DEFAULT 1, name TEXT NOT NULL,
            posting_date TEXT NOT NULL, user_remark TEXT DEFAULT '',
            total_debit REAL NOT NULL DEFAULT 0, docstatus INTEGER NOT NULL DEFAULT 1,
            creation TEXT NOT NULL, PRIMARY KEY (tenant, name))""",
        "tenant, name, posting_date, user_remark, total_debit, docstatus, creation"),
    "money_accounts": (
        """CREATE TABLE money_accounts_new (
            tenant INTEGER NOT NULL DEFAULT 1, account TEXT NOT NULL,
            kind TEXT, ord INTEGER DEFAULT 0, currency TEXT DEFAULT 'KRW',
            label TEXT, PRIMARY KEY (tenant, account))""",
        "tenant, account, kind, ord, currency, label"),
    "catalog_i18n": (
        """CREATE TABLE catalog_i18n_new (
            tenant INTEGER NOT NULL DEFAULT 1, account TEXT NOT NULL,
            ru TEXT, en TEXT, ko TEXT, PRIMARY KEY (tenant, account))""",
        "tenant, account, ru, en, ko"),
    "entry_meta": (
        """CREATE TABLE entry_meta_new (
            tenant INTEGER NOT NULL DEFAULT 1, voucher TEXT NOT NULL,
            occurred_at TEXT NOT NULL, PRIMARY KEY (tenant, voucher))""",
        "tenant, voucher, occurred_at"),
    "user_settings": (
        """CREATE TABLE user_settings_new (
            tenant INTEGER NOT NULL DEFAULT 1, key TEXT NOT NULL,
            value TEXT NOT NULL, PRIMARY KEY (tenant, key))""",
        "tenant, key, value"),
    "led_seq": (
        """CREATE TABLE led_seq_new (
            tenant INTEGER NOT NULL DEFAULT 1, year TEXT NOT NULL,
            n INTEGER NOT NULL, PRIMARY KEY (tenant, year))""",
        "tenant, year, n"),
}


def main():
    bak = DB.parent / f"counta.db.pre-tenantpk-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(DB, bak)
    print("бэкап:", bak.name)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=OFF")
    for tbl, (create_sql, cols) in REBUILDS.items():
        pk = [r[1] for r in con.execute(f"PRAGMA table_info({tbl})") if r[5]]
        if len(pk) >= 2:
            print(f"  {tbl}: уже композитный PK {pk} — пропуск")
            continue
        have = {r[1] for r in con.execute(f"PRAGMA table_info({tbl})")}
        if "tenant" not in have:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
        con.execute(f"DROP TABLE IF EXISTS {tbl}_new")
        con.execute(create_sql)
        con.execute(f"INSERT INTO {tbl}_new ({cols}) SELECT {cols} FROM {tbl}")
        n = con.execute(f"SELECT COUNT(*) FROM {tbl}_new").fetchone()[0]
        con.execute(f"DROP TABLE {tbl}")
        con.execute(f"ALTER TABLE {tbl}_new RENAME TO {tbl}")
        print(f"  {tbl}: пересоздан с PK(tenant,…), строк перенесено {n}")
    con.commit()
    con.close()
    print("✅ миграция PK завершена")


if __name__ == "__main__":
    sys.exit(main())
