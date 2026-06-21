#!/usr/bin/env python3
"""Очистить в аккаунте владельца (OWNER_TENANT_ID) пустые категории,
которые не входят в канонический дефолтный набор.

Пустая = ни одной строки в led_lines (включая отменённые проводки).
Недефолтная = не входит в counta.core.catalog.DEFAULT_KEYS.

Запускать вручную, с --apply для реального удаления."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from counta.core.catalog import DEFAULT_KEYS, canon_key
from counta.core.db import DB_PATH
from counta.core.tenant import OWNER_TENANT_ID

DEFAULT_PKS = {canon_key(k) for k in DEFAULT_KEYS}


def main(dry_run: bool = True) -> int:
    if not DB_PATH.exists():
        print(f"БД не найдена: {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=OFF")
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT name, account_name, root_type FROM led_accounts "
        "WHERE tenant=? AND root_type IN ('Expense','Income')",
        (OWNER_TENANT_ID,),
    ).fetchall()

    to_delete = []
    for r in rows:
        if r["name"] in DEFAULT_PKS:
            continue
        active = con.execute(
            "SELECT COUNT(DISTINCT l.entry) FROM led_lines l "
            "JOIN led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
            "WHERE l.tenant=? AND l.account=? AND e.docstatus=1",
            (OWNER_TENANT_ID, r["name"]),
        ).fetchone()[0]
        if active == 0:
            to_delete.append(r["name"])

    print(f"Владелец (tenant {OWNER_TENANT_ID}): найдено {len(to_delete)} пустых недефолтных категорий для удаления")
    for name in to_delete:
        print(f"  - {name}")

    if dry_run:
        print("\nСУХОЙ ПРОГОН. Для удаления добавь --apply")
        con.close()
        return 0

    if not to_delete:
        con.close()
        return 0

    ph = ",".join("?" * len(to_delete))

    entries = [r["entry"] for r in con.execute(
        f"SELECT DISTINCT entry FROM led_lines WHERE tenant=? AND account IN ({ph})",
        (OWNER_TENANT_ID, *to_delete),
    ).fetchall()]

    deleted_lines = 0
    deleted_entries = 0
    if entries:
        eph = ",".join("?" * len(entries))
        deleted_lines = con.execute(
            f"DELETE FROM led_lines WHERE tenant=? AND entry IN ({eph})",
            (OWNER_TENANT_ID, *entries),
        ).rowcount
        deleted_entries = con.execute(
            f"DELETE FROM led_entries WHERE tenant=? AND name IN ({eph})",
            (OWNER_TENANT_ID, *entries),
        ).rowcount

    deleted_i18n = con.execute(
        f"DELETE FROM catalog_i18n WHERE tenant=? AND account IN ({ph})",
        (OWNER_TENANT_ID, *to_delete),
    ).rowcount

    deleted_accs = con.execute(
        f"DELETE FROM led_accounts WHERE tenant=? AND name IN ({ph})",
        (OWNER_TENANT_ID, *to_delete),
    ).rowcount

    con.commit()
    con.close()

    print(f"\nУдалено:")
    print(f"  категорий: {deleted_accs}")
    print(f"  переводов: {deleted_i18n}")
    print(f"  проводок (отменённых): {deleted_entries}")
    print(f"  строк GL: {deleted_lines}")
    return 0


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    sys.exit(main(dry_run=dry))
