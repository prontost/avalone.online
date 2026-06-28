"""Реестр денежных счетов пользователя (касса / банк / карты / будущие).

Этот модуль теперь является обратно-совместимым фасадом над
:class:`MoneyAccountService`. Вся бизнес-логика и SQL живут в
``money_account_service.py`` и ``money_account_repository.py``.
"""

from __future__ import annotations

from avalone_finance.core.money_account_service import (
    DEFAULT_CURRENCY,
    NATIVE_MONEY_TYPES,
    MoneyAccountService,
)

# Re-exported constants (imported here so they stay available as money.*).
NATIVE_MONEY_TYPES = NATIVE_MONEY_TYPES
DEFAULT_CURRENCY = DEFAULT_CURRENCY

_default_service = MoneyAccountService()


def set_label(account: str, label: str) -> None:
    _default_service.set_label(account, label)


def account_label(account: str) -> str | None:
    return _default_service.account_label(account)


def register(
    account: str,
    kind: str = "other",
    ord: int = 0,
    currency: str | None = None,
) -> None:
    _default_service.register(account, kind, ord, currency)


def set_currency(account: str, currency: str) -> None:
    _default_service.set_currency(account, currency)


def unregister(account: str) -> None:
    _default_service.unregister(account)


def registered() -> dict[str, str]:
    return _default_service.registered()


def registered_full() -> dict[str, dict]:
    return _default_service.registered_full()


def account_currency(account: str) -> str:
    return _default_service.account_currency(account)


def is_money(account: str, account_type: str | None = None) -> bool:
    return _default_service.is_money(account, account_type)


async def ensure_money_seed() -> int:
    return await _default_service.ensure_money_seed()
