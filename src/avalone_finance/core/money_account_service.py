"""Business-logic service for the money account registry.

This is the class-based, dependency-injectable implementation of the behaviour
that previously lived in ``avalone_finance.core.money``. The module-level API in
``money.py`` is kept as a thin facade over a default service instance.
"""

from __future__ import annotations

from typing import Any

# account_type values that ERPNext itself treats as money
NATIVE_MONEY_TYPES = {"Bank", "Cash"}

# Base currency; used as a fallback for legacy rows.
DEFAULT_CURRENCY = "KRW"


class MoneyAccountService:
    """Per-tenant money registry business logic."""

    def __init__(
        self,
        repository: Any | None = None,
        ledger_service: Any | None = None,
        ledger_ops: Any | None = None,
    ) -> None:
        self._repository = repository
        self._ledger_service = ledger_service
        self._ledger_ops = ledger_ops

    # ------------------------------------------------------------------ helpers
    def _tid(self) -> int:
        from avalone_finance.core import tenant
        return tenant.require_current()

    def _repo(self):
        if self._repository is None:
            from avalone_finance.core.money_account_repository import MoneyAccountRepository
            self._repository = MoneyAccountRepository()
        return self._repository

    def _ledger(self):
        if self._ledger_service is None:
            from avalone_finance.core.ledger_service import LedgerService
            self._ledger_service = LedgerService()
        return self._ledger_service

    def _ops(self):
        if self._ledger_ops is None:
            import avalone_finance.core.ledger_ops as ledger_ops
            self._ledger_ops = ledger_ops
        return self._ledger_ops

    def _resolve_tenant(self, tenant: int | None) -> int:
        return tenant if tenant is not None else self._tid()

    # ------------------------------------------------------------------ labels
    def set_label(self, account: str, label: str, tenant: int | None = None) -> None:
        self._repo().set_label(self._resolve_tenant(tenant), account, label.strip())

    def account_label(self, account: str, tenant: int | None = None) -> str | None:
        label = self._repo().account_label(self._resolve_tenant(tenant), account)
        return label if label else None

    # ------------------------------------------------------------------ registry
    def register(
        self,
        account: str,
        kind: str = "other",
        ord: int = 0,
        currency: str | None = None,
        tenant: int | None = None,
    ) -> None:
        update_currency = currency is not None
        cur = (currency or DEFAULT_CURRENCY).upper()
        self._repo().register(
            self._resolve_tenant(tenant),
            account,
            kind,
            ord,
            cur,
            update_currency=update_currency,
        )

    def set_currency(self, account: str, currency: str, tenant: int | None = None) -> None:
        self._repo().set_currency(self._resolve_tenant(tenant), account, currency.upper())

    def unregister(self, account: str, tenant: int | None = None) -> None:
        self._repo().unregister(self._resolve_tenant(tenant), account)

    def registered(self, tenant: int | None = None) -> dict[str, str]:
        return self._repo().registered(self._resolve_tenant(tenant))

    def registered_full(self, tenant: int | None = None) -> dict[str, dict]:
        tid = self._resolve_tenant(tenant)
        rows = self._repo().registered_full(tid)
        return {
            account: {
                "kind": info["kind"],
                "ord": info["ord"],
                "currency": info["currency"] or DEFAULT_CURRENCY,
            }
            for account, info in rows.items()
        }

    def account_currency(self, account: str, tenant: int | None = None) -> str:
        cur = self._repo().account_currency(self._resolve_tenant(tenant), account)
        return cur if cur else DEFAULT_CURRENCY

    def is_money(self, account: str, account_type: str | None = None, tenant: int | None = None) -> bool:
        """Money if it is natively typed as Bank/Cash or present in the registry."""
        if account_type in NATIVE_MONEY_TYPES:
            return True
        return account in self.registered(tenant)

    # ------------------------------------------------------------------ seeding
    async def ensure_money_seed(self, tenant: int | None = None) -> int:
        """Idempotently seed the registry from the current chart of accounts."""
        tid = self._resolve_tenant(tenant)
        if self.registered(tid):
            return 0
        accounts = self._ledger().list_accounts()
        n = 0
        for kind in ("cash", "bank", "credit_card"):
            acc = self._ops().resolve_money_account(kind, accounts)
            if acc:
                self.register(acc, kind, n, tenant=tid)
                n += 1
        return n
