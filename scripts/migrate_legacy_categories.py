#!/usr/bin/env python3
"""Удалить устаревшие (неканонические) категории и все их проводки
для всех пользователей, кроме владельца (OWNER_TENANT_ID=1).

Владелец сам перенесёт свои записи в канонические категории.
Данные остальных пользователей — тестовые/фейковые, их можно удалить.

Запускать только вручную и только после бэкапа БД.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from counta.core.catalog import CANON, canon_key
from counta.core.db import DB_PATH
from counta.core.tenant import OWNER_TENANT_ID


CANON_KEYS = {canon_key(name) for name in CANON}


def canon_for_root(root_type: str) -> set[str]:
    return {canon_key(name) for name, meta in CANON.items() if meta["root"] == root_type}


def main(dry_run: bool = True) -> int:
    if not DB_PATH.exists():
        print(f"БД не найдена: {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=OFF")
    con.row_factory = sqlite3.Row

    tenants = [r["id"] for r in con.execute("SELECT id FROM users ORDER BY id")]
    print(f"Найдено {len(tenants)} пользователей, OWNER_TENANT_ID={OWNER_TENANT_ID}")

    total_accs = 0
    total_entries = 0
    total_lines = 0
    total_i18n = 0

    for tid in tenants:
        if tid == OWNER_TENANT_ID:
            print(f"  skip tenant {tid}: owner")
            continue

        # неканонические Expense/Income счета
        rows = con.execute(
            "SELECT name, root_type FROM led_accounts "
            "WHERE tenant=? AND root_type IN ('Expense','Income')",
            (tid,),
        ).fetchall()
        bad = [r["name"] for r in rows if r["name"] not in canon_for_root(r["root_type"])]
        if not bad:
            print(f"  tenant {tid}: нет устаревших категорий")
            continue

        print(f"  tenant {tid}: {len(bad)} устаревших категорий")
        ph = ",".join("?" * len(bad))

        # проводки, в которых участвуют эти категории (любая сторона)
        entry_rows = con.execute(
            f"SELECT DISTINCT entry FROM led_lines WHERE tenant=? AND account IN ({ph})",
            (tid, *bad),
        ).fetchall()
        entries = [r["entry"] for r in entry_rows]
        print(f"    затронуто проводок: {len(entries)}")

        if dry_run:
            total_accs += len(bad)
            total_entries += len(entries)
            continue

        # удалить строки и сами проводки
        if entries:
            eph = ",".join("?" * len(entries))
            cur_lines = con.execute(
                f"DELETE FROM led_lines WHERE tenant=? AND entry IN ({eph})",
                (tid, *entries),
            ).rowcount
            cur_entries = con.execute(
                f"DELETE FROM led_entries WHERE tenant=? AND name IN ({eph})",
                (tid, *entries),
            ).rowcount
            total_lines += cur_lines
            total_entries += cur_entries

        # удалить переводы категорий
        cur_i18n = con.execute(
            f"DELETE FROM catalog_i18n WHERE tenant=? AND account IN ({ph})",
            (tid, *bad),
        ).rowcount
        total_i18n += cur_i18n

        # удалить сами счета
        cur_accs = con.execute(
            f"DELETE FROM led_accounts WHERE tenant=? AND name IN ({ph})",
            (tid, *bad),
        ).rowcount
        total_accs += cur_accs

    if not dry_run:
        con.commit()

    print("\nИтого:")
    print(f"  удалено категорий: {total_accs}")
    print(f"  удалено проводок:  {total_entries}")
    print(f"  удалено строк GL:  {total_lines}")
    print(f"  удалено переводов: {total_i18n}")
    print(f"  режим: {'сухой прогон' if dry_run else 'ЗАПИСЬ'}")

    con.close()
    return 0


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    if dry:
        print("СУХОЙ ПРОГОН. Для реального удаления добавь --apply\n")
    sys.exit(main(dry_run=dry))
