"""Deterministic bookkeeping helpers — account resolution and options.

Бизнес-логика живёт в :class:`LedgerOpsService`. Модуль-уровень — тонкий
фасад над дефолтным экземпляром.
"""

from __future__ import annotations

import logging
from typing import Any

from avalone_finance.core.money_account_service import MoneyAccountService

log = logging.getLogger(__name__)

# hint -> substrings to find the account in the live chart (lowercase)
HINT_KEYWORDS = {
    "cash":        ("налич", "cash", "касса", "현금"),
    "bank":        ("банк", "bank", "은행"),
    "credit_card": ("кредит", "credit", "신용"),
}
INCOME_KEYWORDS = {
    "salary":   ("зарплат", "salary", "급여"),
    "side_job": ("подработ", "side", "part"),
    "other":    ("проч", "other", "misc", "기타"),
}
FALLBACK_EXPENSE = ("проч", "other", "misc", "기타")


# ERPNext party-accounts (Debtors/Creditors etc.) require Party fields on every
# entry — they are not usable for simple personal bookkeeping and must never
# win name resolution (e.g. "credit" is a substring of "Creditors").
_EXCLUDED_ACCOUNT_TYPES = {"Receivable", "Payable"}


# деньги: cash/bank — активы; кредитка — обязательство. Жёсткая типизация
# отсекает системные счета вроде «Bank Overdraft Account» (liability с "bank").
_MONEY_ROOT = {"cash": ("Asset",), "bank": ("Asset",), "credit_card": ("Liability",)}


class LedgerOpsService:
    """Helpers for resolving accounts against the live chart."""

    _EXCLUDED_ACCOUNT_TYPES = _EXCLUDED_ACCOUNT_TYPES

    def __init__(self, money_service: MoneyAccountService | None = None) -> None:
        self._money_service = money_service

    def _money(self) -> Any:
        if self._money_service is None:
            from avalone_finance.core import money as _money_module
            self._money_service = _money_module
        return self._money_service

    def _find_account(
        self,
        accounts: list[dict],
        keywords: tuple,
        root_types: tuple,
    ) -> str | None:
        for a in accounts:
            if a.get("account_type") in self._EXCLUDED_ACCOUNT_TYPES:
                continue
            if a["root_type"] in root_types and any(k in a["name"].lower() for k in keywords):
                return a["name"]
        return None

    def resolve_money_account(
        self,
        hint: str | None,
        accounts: list[dict],
    ) -> str | None:
        """cash/bank/credit_card -> exact account name from the live chart."""
        if not hint:
            return None
        kw = HINT_KEYWORDS.get(hint)
        if not kw:
            return None
        return self._find_account(accounts, kw, _MONEY_ROOT[hint])

    def resolve_expense_account(
        self,
        category: str | None,
        accounts: list[dict],
    ) -> str | None:
        """Category word -> expense account, ONLY on a confident match.

        Никакого «ближайшего похожего» молча: нет уверенного совпадения — None,
        и выше по стеку пользователь получит выбор (план счетов принадлежит ему).
        """
        if not category:
            return None
        expenses = [a for a in accounts if a.get("account_type") not in self._EXCLUDED_ACCOUNT_TYPES
                    and a["root_type"] == "Expense"]
        cat = category.lower()
        for a in expenses:
            name = a["account_name"].lower()
            if cat == name or cat in name or name in cat:
                return a["name"]
        for a in expenses:
            if any(t and len(t) > 2 and t in a["account_name"].lower() for t in cat.split()):
                return a["name"]
        return None

    def similar_expense_accounts(
        self,
        category: str | None,
        accounts: list[dict],
        n: int = 3,
    ) -> list[str]:
        """Top-n candidate expense accounts to offer as buttons."""
        expenses = [a["account_name"] for a in accounts if a["root_type"] == "Expense"
                    and a.get("account_type") not in self._EXCLUDED_ACCOUNT_TYPES]
        if not category:
            return expenses[:n]
        cat = set(category.lower())
        scored = sorted(expenses, key=lambda name: -len(cat & set(name.lower())))
        return scored[:n]

    def money_options(self, accounts: list[dict]) -> list[tuple[str, str]]:
        """Все денежные счета пользователя как (account_name, name) — единообразно.

        Кредитка, наличка, дебетовый счёт — ОДИН и тот же объект: счёт с балансом.
        Никакого деления актив/обязательство в логике: источник истины — реестр money
        (любой счёт равноправен) плюс счета с нативным типом Bank/Cash. Порядок —
        как пользователь их добавил (ord реестра), затем нативные доп. счета по имени.
        Знак баланса (минус = долг) виден одинаково у любого счёта (см. /api/balances)."""
        money = self._money()
        reg = money.registered()                      # dict в порядке ord
        by_name = {a["name"]: a for a in accounts
                   if not a.get("is_group")
                   and a["root_type"] in ("Asset", "Liability")
                   and a.get("account_type") not in self._EXCLUDED_ACCOUNT_TYPES}
        out, seen = [], set()
        for pk in reg:                                # сначала реестр, в порядке добавления
            a = by_name.get(pk)
            if a:
                out.append(a)
                seen.add(pk)
        extra = sorted((a for n, a in by_name.items()
                        if n not in seen and a.get("account_type") in money.NATIVE_MONEY_TYPES),
                       key=lambda a: a["account_name"].lower())
        out += extra
        return [(a["account_name"], a["name"]) for a in out]

    def resolve_income_account(
        self,
        kind: str | None,
        accounts: list[dict],
    ) -> str | None:
        kw = INCOME_KEYWORDS.get(kind or "other", INCOME_KEYWORDS["other"])
        return (self._find_account(accounts, kw, ("Income",))
                or self._find_account(accounts, INCOME_KEYWORDS["other"], ("Income",)))

    async def expense_categories(self, accounts: list[dict]) -> list[str]:
        return [a["account_name"] for a in accounts if a["root_type"] == "Expense"]


# --------------------------------------------------------------------------- #
# Backward-compatible module-level facade
_default_service: LedgerOpsService | None = None


def _service() -> LedgerOpsService:
    global _default_service
    if _default_service is None:
        _default_service = LedgerOpsService()
    return _default_service


def _find_account(accounts: list[dict], keywords: tuple, root_types: tuple) -> str | None:
    return _service()._find_account(accounts, keywords, root_types)


def resolve_money_account(hint: str | None, accounts: list[dict]) -> str | None:
    return _service().resolve_money_account(hint, accounts)


def resolve_expense_account(category: str | None, accounts: list[dict]) -> str | None:
    return _service().resolve_expense_account(category, accounts)


def similar_expense_accounts(
    category: str | None,
    accounts: list[dict],
    n: int = 3,
) -> list[str]:
    return _service().similar_expense_accounts(category, accounts, n)


def money_options(accounts: list[dict]) -> list[tuple[str, str]]:
    return _service().money_options(accounts)


def resolve_income_account(kind: str | None, accounts: list[dict]) -> str | None:
    return _service().resolve_income_account(kind, accounts)


async def expense_categories(accounts: list[dict]) -> list[str]:
    return await _service().expense_categories(accounts)


__all__ = [
    "LedgerOpsService",
    "_EXCLUDED_ACCOUNT_TYPES",
    "HINT_KEYWORDS",
    "INCOME_KEYWORDS",
    "FALLBACK_EXPENSE",
    "resolve_money_account",
    "resolve_expense_account",
    "similar_expense_accounts",
    "money_options",
    "resolve_income_account",
    "expense_categories",
]
