#!/usr/bin/env python3
"""Перенести оставшиеся недефолтные категории владельца в канонические
и удалить пустые недефолтные счета."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from counta.core.db import DB_PATH
from counta.core.tenant import OWNER_TENANT_ID

MAPPING: dict[str, str] = {
    "cat_groceries": "cat_food",
    "cat_health": "cat_health_wellness",
    "cat_household": "cat_other_expense",
    "cat_housing_rent": "cat_housing",
    "cat_phone_internet": "cat_other_expense",
    "cat_taxi": "cat_transport",
    "cat_tobacco": "cat_other_expense",
    "cat_gifts": "cat_other_expense",
    "Бизнес - DP": "cat_other_expense",
    "cat_refund_income": "cat_other_income",
    "cat_tax_refund_income": "cat_other_income",
}


def main(dry_run: bool = True) -> int:
    if not DB_PATH.exists():
        print(f"БД не найдена: {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=OFF")
    con.row_factory = sqlite3.Row

    total_moved = 0
    total_deleted = 0

    print(f"Перенос категорий владельца (tenant {OWNER_TENANT_ID}):")
    for old_pk, new_pk in MAPPING.items():
        active = con.execute(
            "SELECT COUNT(DISTINCT l.entry) FROM led_lines l "
            "JOIN led_entries e ON e.tenant=l.tenant AND e.name=l.entry "
            "WHERE l.tenant=? AND l.account=? AND e.docstatus=1",
            (OWNER_TENANT_ID, old_pk),
        ).fetchone()[0]
        print(f"  {old_pk:<35} → {new_pk:<25} записей={active}")
        if dry_run:
            continue
        if active:
            moved = con.execute(
                "UPDATE led_lines SET account=? WHERE tenant=? AND account=?",
                (new_pk, OWNER_TENANT_ID, old_pk),
            ).rowcount
            total_moved += moved
            # обновить личный лексикон
            con.execute(
                "UPDATE lexicon SET account=? WHERE chat_id=? AND account=?",
                (new_pk, OWNER_TENANT_ID, old_pk),
            )
        # удалить переводы и сам счёт (строк уже нет)
        con.execute(
            "DELETE FROM catalog_i18n WHERE tenant=? AND account=?",
            (OWNER_TENANT_ID, old_pk),
        )
        deleted = con.execute(
            "DELETE FROM led_accounts WHERE tenant=? AND name=?",
            (OWNER_TENANT_ID, old_pk),
        ).rowcount
        total_deleted += deleted

    if not dry_run:
        con.commit()

    print(f"\nИтого ({'сухой прогон' if dry_run else 'ЗАПИСЬ'}):")
    print(f"  перенесено строк GL: {total_moved}")
    print(f"  удалено категорий:   {total_deleted}")
    con.close()
    return 0


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    sys.exit(main(dry_run=dry))
