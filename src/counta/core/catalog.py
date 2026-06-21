"""Canonical personal-finance categories + localized labels.

Categories are intentionally minimal (~12 expense + ~4 income) so that
analytics, tips and the 50/30/20 rule stay readable. Every category has a
role: need / want / goal."""

import sqlite3

from counta.core.db import DB_PATH

# canonical EN account_name -> {root, role, ru, en, ko}
# role: need | want | goal (used by analytics and tips)
CANON: dict[str, dict] = {
    # --- NEEDS (обязательные траты) ---
    "Housing":          {"root": "Expense", "role": "need",
                         "ru": "Жильё", "en": "Housing", "ko": "주거"},
    "Food":             {"root": "Expense", "role": "need",
                         "ru": "Продукты", "en": "Food", "ko": "식료품"},
    "Transport":        {"root": "Expense", "role": "need",
                         "ru": "Транспорт", "en": "Transport", "ko": "교통"},
    "Health & wellness":{"root": "Expense", "role": "need",
                         "ru": "Здоровье и уход", "en": "Health & wellness", "ko": "건강 및 관리"},
    "Family & kids":    {"root": "Expense", "role": "need",
                         "ru": "Семья и дети", "en": "Family & kids", "ko": "가족 및 아이"},

    # --- WANTS (лайфстайл, можно сократить) ---
    "Eating out":       {"root": "Expense", "role": "want",
                         "ru": "Кафе и рестораны", "en": "Eating out", "ko": "외식"},
    "Shopping & stuff": {"root": "Expense", "role": "want",
                         "ru": "Покупки и вещи", "en": "Shopping & stuff", "ko": "쇼핑 및 물건"},
    "Fun & subscriptions":{"root": "Expense", "role": "want",
                         "ru": "Развлечения и подписки", "en": "Fun & subscriptions", "ko": "여가 및 구독"},
    "Travel":           {"root": "Expense", "role": "want",
                         "ru": "Путешествия", "en": "Travel", "ko": "여행"},
    "Other expense":    {"root": "Expense", "role": "want",
                         "ru": "Прочее", "en": "Other", "ko": "기타"},
    "Uncategorized":    {"root": "Expense", "role": "want",
                         "ru": "Укажу позже", "en": "Set later", "ko": "나중에 지정"},

    # --- GOALS (финансовое будущее) ---
    "Savings & investments":{"root": "Expense", "role": "goal",
                         "ru": "Сбережения и инвестиции", "en": "Savings & investments", "ko": "저축 및 투자"},
    "Debt repayment":   {"root": "Expense", "role": "goal",
                         "ru": "Погашение долгов", "en": "Debt repayment", "ko": "빚 상환"},
    "Education & growth":{"root": "Expense", "role": "goal",
                         "ru": "Образование и рост", "en": "Education & growth", "ko": "교육 및 성장"},

    # --- INCOME ---
    "Salary income":    {"root": "Income", "role": "income",
                         "ru": "Зарплата", "en": "Salary", "ko": "급여"},
    "Side income":      {"root": "Income", "role": "income",
                         "ru": "Подработка", "en": "Side income", "ko": "부수입"},
    "Passive income":   {"root": "Income", "role": "income",
                         "ru": "Пассивный доход", "en": "Passive income", "ko": "패시브 소득"},
    "Other income":     {"root": "Income", "role": "income",
                         "ru": "Прочий доход", "en": "Other income", "ko": "기타 수입"},
}

# Мультиюзер: переводы категорий у каждого тенанта свои. PK (tenant, account).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_i18n (
    tenant INTEGER NOT NULL DEFAULT 1,
    account TEXT NOT NULL,
    ru TEXT, en TEXT, ko TEXT,
    PRIMARY KEY (tenant, account)
);
"""


def _tid() -> int:
    from counta.core import tenant
    return tenant.require_current()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(catalog_i18n)")}
    if "tenant" not in cols:
        con.execute("ALTER TABLE catalog_i18n ADD COLUMN tenant INTEGER NOT NULL DEFAULT 1")
    return con


def set_labels(account: str, ru: str, en: str, ko: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO catalog_i18n (tenant, account, ru, en, ko) VALUES (?,?,?,?,?) "
            "ON CONFLICT(tenant, account) DO UPDATE SET ru=excluded.ru, en=excluded.en, ko=excluded.ko",
            (_tid(), account, ru, en, ko))


def forget_labels(account: str) -> None:
    """Стереть переводы ярлыка из catalog_i18n (при окончательном удалении)."""
    with _conn() as con:
        con.execute("DELETE FROM catalog_i18n WHERE tenant=? AND account=?", (_tid(), account))


def _user_labels() -> dict[str, dict]:
    with _conn() as con:
        rows = con.execute("SELECT account, ru, en, ko FROM catalog_i18n WHERE tenant=?",
                           (_tid(),)).fetchall()
    return {r[0]: {"ru": r[1], "en": r[2], "ko": r[3]} for r in rows}


def label(account: str, account_name: str, lang: str = "ru") -> str:
    """Localized label for an account. Priority: user table -> canon -> glossary."""
    users = _user_labels()
    if account in users and users[account].get(lang):
        return users[account][lang]
    from counta.core import glossary
    if account.startswith("cat_"):
        g = glossary.get(account, lang)
        if g != account:
            return g
    base = account_name
    if base in CANON:
        key = canon_key(base)
        g = glossary.get(key, lang)
        if g != key:
            return g
        if CANON[base].get(lang):
            return CANON[base][lang]
    return account_name


def canon_key(account_name: str) -> str:
    """Нейтральный цифробуквенный ключ глоссария: 'Eating out' -> cat_eating_out."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", account_name.lower()).strip("_")
    return f"cat_{slug}"


def role(account_name: str) -> str:
    """Role of a canonical category: need | want | goal | income | ''."""
    meta = CANON.get(account_name)
    return meta.get("role", "") if meta else ""


def seed_glossary() -> int:
    """Засеять канонические категории/доходы в единый глоссарий (kind='category')."""
    from counta.core import glossary
    rows = []
    for name, meta in CANON.items():
        is_income = meta.get("root") == "Income"
        role = meta.get("role", "")
        role_desc = {
            "need": "a basic need (must-have spending)",
            "want": "a lifestyle want (discretionary spending)",
            "goal": "a financial goal (savings, debt, self-investment)",
            "income": "an income source",
        }.get(role, "a personal finance category")
        desc = (f"Name of {role_desc} in a personal finance app. "
                f"Canonical English term: '{meta.get('en', name)}'. "
                f"Translate as the natural everyday word a person uses for this.")
        rows.append({"key": canon_key(name), "ru": meta.get("ru", ""),
                     "en": meta.get("en", ""), "ko": meta.get("ko", ""),
                     "kind": "category", "desc": desc})
    return glossary.upsert_many(rows)


def known_accounts() -> set[str]:
    """Полные имена счетов, у которых есть пользовательские переводы."""
    return set(_user_labels())


def is_user_category(account: str) -> bool:
    """Заведена ли пользователем (есть запись в catalog_i18n)."""
    return account in known_accounts()


# Базовый набор для нового пользователя.
DEFAULT_KEYS = [
    # needs
    "Housing", "Food", "Transport", "Health & wellness", "Family & kids",
    # wants
    "Eating out", "Shopping & stuff", "Fun & subscriptions", "Travel",
    "Other expense", "Uncategorized",
    # goals
    "Savings & investments", "Debt repayment", "Education & growth",
    # income
    "Salary income", "Side income", "Passive income", "Other income",
]


async def ensure_user_catalog() -> int:
    """Идемпотентно создать недостающие базовые категории в леджере
    и проставить им переводы. Возвращает число созданных."""
    import logging
    from counta.core import engine, sqlledger

    all_accs = await engine.list_accounts(leaf_only=False, include_disabled=True)
    pks = {a["name"] for a in all_accs}
    labelled = known_accounts()
    created = 0
    for key in DEFAULT_KEYS:
        meta = CANON[key]
        full = canon_key(key)
        if full not in pks:
            try:
                sqlledger.create_account_id(full, key, meta["root"])
                created += 1
            except Exception:
                logging.getLogger(__name__).warning("ensure_user_catalog: не создать %s", key)
                continue
        if full not in labelled:
            set_labels(full, meta["ru"], meta["en"], meta["ko"])
    return created
