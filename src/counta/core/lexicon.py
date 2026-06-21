"""Per-user learned lexicon: the user's words -> their accounts.

Третий слой архитектуры (Дэн, 2026-06-12): знания о словаре пользователя — это
ДАННЫЕ, не код и не промпт. «Карта» у одного — дебетовая, у другого — кредитка;
бот не угадывает: незнакомое слово -> один вопрос с вариантами -> ответ
сохраняется здесь навсегда. Каждое исправление тоже учит лексикон.
План счетов принадлежит пользователю: незнакомая категория -> выбор из похожих
/ создать новый счёт — никогда не форсить в «ближайший» молча.
"""

import sqlite3
from datetime import datetime, timezone

from counta.core.db import DB_PATH  # единый файл БД приложения

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lexicon (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    kind TEXT NOT NULL,           -- 'money' | 'category'
    phrase TEXT NOT NULL,         -- normalized user word(s)
    account TEXT NOT NULL,        -- exact ERPNext account name
    ts TEXT NOT NULL,
    UNIQUE(chat_id, kind, phrase)
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    return con


_PREPOSITIONS = {"с", "со", "на", "из", "в", "за", "по", "от", "к"}


def _stem(word: str) -> str:
    # грубый стем: «карты/картой/картах» -> «карт». Для личного лексикона
    # (десятки слов, один пользователь) ложные склейки практически исключены.
    return word[:4] if len(word) > 4 else word


def _norm(phrase: str) -> str:
    words = [_stem(w) for w in phrase.lower().split() if w not in _PREPOSITIONS]
    return " ".join(words)


def lookup(chat_id: int, kind: str, phrase: str) -> str | None:
    """Exact normalized match, then containment either way («карта кб» ~ «карты кб
    банка») — человек никогда не повторяет фразу буквально."""
    p = _norm(phrase or "")
    if not p:
        return None
    with _conn() as con:
        rows = con.execute(
            "SELECT phrase, account FROM lexicon WHERE chat_id=? AND kind=? ORDER BY length(phrase) DESC",
            (chat_id, kind)).fetchall()
    for saved, account in rows:
        if saved == p or saved in p or p in saved:
            return account
    return None


def save(chat_id: int, kind: str, phrase: str, account: str) -> None:
    if not phrase:
        return
    with _conn() as con:
        con.execute(
            "INSERT INTO lexicon (chat_id, kind, phrase, account, ts) VALUES (?,?,?,?,?) "
            "ON CONFLICT(chat_id, kind, phrase) DO UPDATE SET account=excluded.account, ts=excluded.ts",
            (chat_id, kind, _norm(phrase), account,
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
