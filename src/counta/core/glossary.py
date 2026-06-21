"""Единый глоссарий — единственный источник истины для ВСЕХ слов системы.

Принцип Дэна (2026-06-15): всё, что видит пользователь, и «слова за кадром» —
в одном глоссарии. Базовый идентификатор — ЦИФРОБУКВЕННЫЙ КЛЮЧ, а не слово на
каком-либо языке. Все языки (включая русский) — переводы ключа; ни один язык не
является «основой».

Этап C (фундамент): таблица + загрузчик + перенос UI-строк сюда как источник.
Этапы B/A далее подключат доменные строки (валюты, уведомления) и нормализуют
словесные ключи категорий (`Groceries` -> `cat_groceries`).

Таблица:
    glossary(key TEXT PK, ru TEXT, en TEXT, ko TEXT, kind TEXT)
- key  — цифробуквенный (f_category, edit_incomes, cur_usd, ...)
- ru/en/ko — переводы; пусто = ключ ещё не переведён на этот язык
- kind — группа (ui | category | currency | notif | ...) для будущей навигации
"""

import sqlite3

from counta.core.db import DB_PATH

LANGS = ("ru", "en", "ko")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS glossary (
    key  TEXT PRIMARY KEY,
    ru   TEXT,
    en   TEXT,
    ko   TEXT,
    kind TEXT DEFAULT 'ui',
    desc TEXT DEFAULT ''   -- метаописание: ЧТО за слово, ГДЕ показывается, какая
                           -- роль/контекст. Нужно ИИ для осмысленного перевода на
                           -- произвольные языки (иначе «Cash» → наугад).
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    # миграция: добить desc на старых БД, где колонки не было
    cols = {r[1] for r in con.execute("PRAGMA table_info(glossary)")}
    if "desc" not in cols:
        con.execute("ALTER TABLE glossary ADD COLUMN desc TEXT DEFAULT ''")
    return con


def upsert(key: str, ru: str = "", en: str = "", ko: str = "", kind: str = "ui",
           desc: str | None = None) -> None:
    upsert_many([{"key": key, "ru": ru, "en": en, "ko": ko, "kind": kind, "desc": desc}])


def upsert_many(rows: list[dict]) -> int:
    """rows: [{key, ru, en, ko, kind?, desc?}, ...]. Возвращает число записанных.

    desc=None (или ключ отсутствует) → НЕ затираем существующее метаописание
    (сиды из Python-словарей не должны стирать вручную написанные desc).
    desc="" → явно очистить."""
    with _conn() as con:
        for r in rows:
            desc = r.get("desc")
            if desc is None:
                con.execute(
                    "INSERT INTO glossary (key, ru, en, ko, kind, desc) VALUES (?,?,?,?,?,'') "
                    "ON CONFLICT(key) DO UPDATE SET ru=excluded.ru, en=excluded.en, "
                    "ko=excluded.ko, kind=excluded.kind",
                    (r["key"], r.get("ru", ""), r.get("en", ""), r.get("ko", ""),
                     r.get("kind", "ui")))
            else:
                con.execute(
                    "INSERT INTO glossary (key, ru, en, ko, kind, desc) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET ru=excluded.ru, en=excluded.en, "
                    "ko=excluded.ko, kind=excluded.kind, desc=excluded.desc",
                    (r["key"], r.get("ru", ""), r.get("en", ""), r.get("ko", ""),
                     r.get("kind", "ui"), desc))
    return len(rows)


def set_desc(key: str, desc: str) -> None:
    """Задать/исправить метаописание ключа (для редактора глоссария / правок)."""
    with _conn() as con:
        con.execute("UPDATE glossary SET desc=? WHERE key=?", (desc, key))


def all_by_lang() -> dict[str, dict[str, str]]:
    """{lang: {key: text}} — формат, удобный фронту (как старый I18N dict)."""
    out: dict[str, dict[str, str]] = {l: {} for l in LANGS}
    with _conn() as con:
        for key, ru, en, ko, _ in con.execute(
                "SELECT key, ru, en, ko, kind FROM glossary"):
            vals = {"ru": ru, "en": en, "ko": ko}
            for l in LANGS:
                if vals[l]:
                    out[l][key] = vals[l]
    return out


def get(key: str, lang: str = "ru") -> str:
    """Перевод ключа на язык; фолбэк ru -> en -> сам ключ."""
    with _conn() as con:
        row = con.execute("SELECT ru, en, ko FROM glossary WHERE key=?", (key,)).fetchone()
    if not row:
        return key
    vals = {"ru": row[0], "en": row[1], "ko": row[2]}
    return vals.get(lang) or vals["ru"] or vals["en"] or key


def entries() -> list[dict]:
    """Полные строки глоссария для редактора/ИИ-перевода:
    [{key, ru, en, ko, kind, desc}, ...]. desc — контекст для осмысленного перевода."""
    with _conn() as con:
        rows = con.execute(
            "SELECT key, ru, en, ko, kind, desc FROM glossary ORDER BY kind, key").fetchall()
    return [{"key": r[0], "ru": r[1], "en": r[2], "ko": r[3],
             "kind": r[4], "desc": r[5] or ""} for r in rows]


def describe(key: str) -> str:
    """Метаописание ключа (контекст). Пусто, если ещё не задано."""
    with _conn() as con:
        row = con.execute("SELECT desc FROM glossary WHERE key=?", (key,)).fetchone()
    return (row[0] if row and row[0] else "")


def missing_desc() -> list[str]:
    """Ключи без метаописания — что осталось описать для качественного ИИ-перевода."""
    with _conn() as con:
        return [r[0] for r in con.execute(
            "SELECT key FROM glossary WHERE desc IS NULL OR desc='' ORDER BY kind, key")]


def count() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM glossary").fetchone()[0]
