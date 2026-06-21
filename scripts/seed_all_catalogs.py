#!/usr/bin/env python3
"""Идемпотентно создать недостающие дефолтные категории всем пользователям."""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from counta.core import catalog, db, tenant


async def _seed(tid: int) -> int:
    tenant.set_current(tid)
    return await catalog.ensure_user_catalog()


def main() -> int:
    if not db.DB_PATH.exists():
        print(f"БД не найдена: {db.DB_PATH}")
        return 1
    con = sqlite3.connect(db.DB_PATH)
    users = con.execute("SELECT id, login FROM users ORDER BY id").fetchall()
    con.close()
    print(f"Засеваю категории для {len(users)} пользователей...")
    for uid, login in users:
        n = asyncio.run(_seed(uid))
        print(f"  tenant {uid} ({login}): создано {n} категорий")
    return 0


if __name__ == "__main__":
    sys.exit(main())
