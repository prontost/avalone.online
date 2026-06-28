"""Business-logic service for canonical personal-finance categories.

This is the class-based, dependency-injectable implementation of the behaviour
that previously lived in ``avalone_finance.core.catalog``. The module-level API
in ``catalog.py`` is kept as a thin facade over a default service instance.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from avalone_finance.core import tenant
from avalone_finance.core.catalog_repository import CatalogRepository


class _DefaultLedgerService:
    """Adapter that exposes the async engine facade and sync sqlledger helpers.

    ``CatalogService.ensure_user_catalog`` is async because it mirrors the old
    module-level API, but account creation itself is synchronous.
    """

    async def list_accounts(
        self,
        *,
        leaf_only: bool = True,
        include_disabled: bool = False,
    ) -> list[dict]:
        import avalone_finance.core.engine as engine
        return await engine.list_accounts(leaf_only=leaf_only, include_disabled=include_disabled)

    def create_account_id(
        self,
        account_id: str,
        account_name: str,
        root_type: str,
        account_type: str = "",
    ) -> str:
        import avalone_finance.core.sqlledger as sqlledger
        return sqlledger.create_account_id(account_id, account_name, root_type, account_type)


# canonical EN account_name -> {root, role}. Display text lives in the unified
# glossary under cat_* keys (kind='category'); see canon_key() and seed_glossary().
CANON: dict[str, dict] = {
    # --- NEEDS ---
    "Housing": {"root": "Expense", "role": "need"},
    "Food": {"root": "Expense", "role": "need"},
    "Transport": {"root": "Expense", "role": "need"},
    "Health & wellness": {"root": "Expense", "role": "need"},
    "Family & kids": {"root": "Expense", "role": "need"},

    # --- WANTS ---
    "Eating out": {"root": "Expense", "role": "want"},
    "Shopping & stuff": {"root": "Expense", "role": "want"},
    "Fun & subscriptions": {"root": "Expense", "role": "want"},
    "Travel": {"root": "Expense", "role": "want"},
    "Other expense": {"root": "Expense", "role": "want"},
    "Uncategorized": {"root": "Expense", "role": "want"},

    # --- GOALS ---
    "Savings & investments": {"root": "Expense", "role": "goal"},
    "Debt repayment": {"root": "Expense", "role": "goal"},
    "Education & growth": {"root": "Expense", "role": "goal"},

    # --- INCOME ---
    "Salary income": {"root": "Income", "role": "income"},
    "Side income": {"root": "Income", "role": "income"},
    "Passive income": {"root": "Income", "role": "income"},
    "Other income": {"root": "Income", "role": "income"},
}

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


class CatalogService:
    """Per-tenant canonical category business logic."""

    CANON = CANON
    DEFAULT_KEYS = DEFAULT_KEYS

    def __init__(
        self,
        repository: CatalogRepository | None = None,
        ledger_service: Any | None = None,
        glossary_service: Any | None = None,
    ) -> None:
        self._repository = repository
        self._ledger_service = ledger_service
        self._glossary_service = glossary_service

    def _tid(self) -> int:
        return tenant.require_current()

    def _repo(self) -> CatalogRepository:
        if self._repository is None:
            self._repository = CatalogRepository()
        return self._repository

    def _ledger(self) -> Any:
        if self._ledger_service is None:
            self._ledger_service = _DefaultLedgerService()
        return self._ledger_service

    def _glossary(self) -> Any:
        if self._glossary_service is None:
            from avalone_finance.core import glossary as _glossary_module
            self._glossary_service = _glossary_module
        return self._glossary_service

    # ------------------------------------------------------------------ labels
    def set_labels(self, account: str, ru: str, en: str, ko: str) -> None:
        self._repo().set_labels(self._tid(), account, ru, en, ko)

    def forget_labels(self, account: str) -> None:
        """Стереть переводы ярлыка из money_catalog_i18n (при окончательном удалении)."""
        self._repo().forget_labels(self._tid(), account)

    def _user_labels(self) -> dict[str, dict]:
        return self._repo().user_labels(self._tid())

    def label(self, account: str, account_name: str, lang: str = "ru") -> str:
        """Localized label for an account. Priority: user table -> canon -> glossary."""
        users = self._user_labels()
        if account in users and users[account].get(lang):
            return users[account][lang]
        glossary = self._glossary()
        if account.startswith("cat_"):
            g = glossary.get(account, lang)
            if g != account:
                return g
        base = account_name
        if base in self.CANON:
            key = self.canon_key(base)
            g = glossary.get(key, lang)
            if g != key:
                return g
        return account_name

    @staticmethod
    def canon_key(account_name: str) -> str:
        """Нейтральный цифробуквенный ключ глоссария: 'Eating out' -> cat_eating_out."""
        slug = re.sub(r"[^a-z0-9]+", "_", account_name.lower()).strip("_")
        return f"cat_{slug}"

    @classmethod
    def role(cls, account_name: str) -> str:
        """Role of a canonical category: need | want | goal | income | ''."""
        meta = cls.CANON.get(account_name)
        return meta.get("role", "") if meta else ""

    # ------------------------------------------------------------------ glossary
    def seed_glossary(self) -> int:
        """Засеять канонические категории/доходы в единый глоссарий (kind='category').

        Translations are taken from the unified glossary itself; this function only
        ensures the canonical cat_* keys are present with their metadata.
        """
        glossary = self._glossary()
        rows = []
        for name, meta in self.CANON.items():
            role = meta.get("role", "")
            role_desc = {
                "need": "a basic need (must-have spending)",
                "want": "a lifestyle want (discretionary spending)",
                "goal": "a financial goal (savings, debt, self-investment)",
                "income": "an income source",
            }.get(role, "a personal finance category")
            key = self.canon_key(name)
            desc = (
                f"Name of {role_desc} in a personal finance app. "
                f"Canonical English term: '{name}'. "
                f"Translate as the natural everyday word a person uses for this."
            )
            rows.append(
                {
                    "key": key,
                    "ru": glossary.t(key, "ru"),
                    "en": glossary.t(key, "en"),
                    "ko": glossary.t(key, "ko"),
                    "kind": "category",
                    "desc": desc,
                }
            )
        return glossary.upsert_many(rows)

    # ------------------------------------------------------------------ registry helpers
    def known_accounts(self) -> set[str]:
        """Полные имена счетов, у которых есть пользовательские переводы."""
        return self._repo().known_accounts(self._tid())

    def is_user_category(self, account: str) -> bool:
        """Заведена ли пользователем (есть запись в money_catalog_i18n)."""
        return self._repo().is_user_category(self._tid(), account)

    # ------------------------------------------------------------------ seeding
    async def ensure_user_catalog(self) -> int:
        """Идемпотентно создать недостающие базовые категории в леджере
        и проставить им переводы. Возвращает число созданных."""
        all_accs = await self._ledger().list_accounts(leaf_only=False, include_disabled=True)
        pks = {a["name"] for a in all_accs}
        labelled = self.known_accounts()
        created = 0
        glossary = self._glossary()
        for key in self.DEFAULT_KEYS:
            meta = self.CANON[key]
            full = self.canon_key(key)
            if full not in pks:
                try:
                    self._ledger().create_account_id(full, key, meta["root"])
                    created += 1
                except Exception:
                    logging.getLogger(__name__).warning("ensure_user_catalog: could not create %s", key)
                    continue
            if full not in labelled:
                cat_key = self.canon_key(key)
                self.set_labels(
                    full,
                    glossary.t(cat_key, "ru"),
                    glossary.t(cat_key, "en"),
                    glossary.t(cat_key, "ko"),
                )
        return created
