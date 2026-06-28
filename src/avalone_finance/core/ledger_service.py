"""Business-logic service for the double-entry finance ledger.

This is the home for all ledger operations that previously lived in
``core/sqlledger.py`` and ``core/engine.py``. It is dependency-injected:
- ``repository`` handles raw SQL (see :class:`LedgerRepository`).
- ``money_service`` answers "is this account money / what currency" questions.
- ``constants_service`` provides tunable constants such as ``find_entry_limit``.

For backward compatibility a default instance of this service is re-exported
through ``core/sqlledger.py`` as module-level functions.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from avalone_core import glossary_db as glossary
from avalone_finance.core import tenant
from avalone_finance.core.ledger_repository import (
    AccountInUseError,
    GlobalImbalanceError,
    LedgerRepository,
    UnbalancedEntriesError,
)


class LedgerError(Exception):
    pass


class _MoneyService(Protocol):
    def is_money(self, account: str, account_type: str | None = None) -> bool: ...
    def account_currency(self, account: str) -> str: ...


class _ConstantsService(Protocol):
    def get(self, name: str) -> Any: ...


class _DefaultMoneyService:
    """Default money-service adapter used by ``LedgerService``.

    The ``MoneyAccountService`` is imported lazily inside each method to avoid
    an import-time circular dependency: ``MoneyAccountService`` itself defaults
    to ``LedgerService`` for seeding, while ``LedgerService`` uses this adapter
    as its default money service.
    """

    def is_money(self, account: str, account_type: str | None = None) -> bool:
        from avalone_finance.core.money_account_service import MoneyAccountService
        return MoneyAccountService().is_money(account, account_type)

    def account_currency(self, account: str) -> str:
        from avalone_finance.core.money_account_service import MoneyAccountService
        return MoneyAccountService().account_currency(account)


class _DefaultConstantsService:
    """Facade around ``avalone_finance.core.constants_service.ConstantsService``."""

    def __init__(self) -> None:
        self._service: Any | None = None

    def get(self, name: str) -> Any:
        if self._service is None:
            from avalone_finance.core.constants_service import ConstantsService
            self._service = ConstantsService()
        return self._service.get(name)


class LedgerService:
    """Business logic for accounts, journal entries, balances and integrity."""

    ABBR = "DP"  # account primary-key suffix (Denis Personal legacy)

    def __init__(
        self,
        repository: LedgerRepository | None = None,
        money_service: _MoneyService | None = None,
        constants_service: _ConstantsService | None = None,
    ) -> None:
        self._repo = repository or LedgerRepository()
        self._money = money_service or _DefaultMoneyService()
        self._constants = constants_service or _DefaultConstantsService()

    def _tid(self) -> int:
        """Current request tenant. Raises if none is set (data-leak guard)."""
        return tenant.require_current()

    def _has_tenant(self) -> bool:
        return bool(tenant.current())

    # ----------------------------------------------------------------- accounts
    def make_pk(self, account_name: str) -> str:
        return f"{account_name} - {self.ABBR}"

    def group_parent(self, root_type: str) -> str | None:
        return None  # flat model — no groups

    def list_accounts(
        self,
        *,
        leaf_only: bool = True,
        include_disabled: bool = False,
    ) -> list[dict]:
        return self._repo.list_accounts(
            self._tid(), leaf_only=leaf_only, include_disabled=include_disabled
        )

    def create_account(
        self,
        account_name: str,
        parent_account: str | None,
        root_type: str,
        account_type: str = "",
    ) -> str:
        return self.create_account_id(
            self.make_pk(account_name), account_name, root_type, account_type
        )

    def create_account_id(
        self,
        account_id: str,
        account_name: str,
        root_type: str,
        account_type: str = "",
    ) -> str:
        return self._repo.create_account_id(
            self._tid(), account_id, account_name, root_type, account_type
        )

    def upsert_account(
        self,
        name: str,
        account_name: str,
        root_type: str,
        account_type: str = "",
        is_group: int = 0,
        disabled: int = 0,
        tenant: int | None = None,
    ) -> None:
        tid = tenant if tenant is not None else self._tid()
        self._repo.upsert_account(
            tid, name, account_name, root_type, account_type, is_group, disabled
        )

    def disable_account(self, name: str) -> None:
        self._repo.disable_account(self._tid(), name)

    def enable_account(self, name: str) -> None:
        self._repo.enable_account(self._tid(), name)

    def delete_account(self, name: str) -> None:
        try:
            self._repo.delete_account(self._tid(), name)
        except AccountInUseError as e:
            raise LedgerError(
                glossary.t("error_account_still_used", lang="ru")
                .replace("{name}", name)
                .replace("{used}", str(e.used))
            )

    # ----------------------------------------------------------------- journal entries
    def post_journal_entry(
        self,
        entry_date: date,
        remark: str,
        debit_account: str,
        credit_account: str,
        amount: Decimal,
        *,
        name: str | None = None,
        creation: str | None = None,
        tenant: int | None = None,
    ) -> str:
        if amount <= 0:
            raise LedgerError(glossary.t("error_amount_must_be_positive", lang="ru"))
        tid = tenant if tenant is not None else self._tid()
        # transfers are allowed only between accounts in the same currency
        if self._money.is_money(debit_account) and self._money.is_money(credit_account):
            if self._money.account_currency(debit_account) != self._money.account_currency(credit_account):
                raise LedgerError(glossary.t("error_transfer_currency_mismatch", lang="ru"))
        return self._repo.post_journal_entry(
            tid, entry_date, remark, debit_account, credit_account, amount,
            name=name, creation=creation,
        )

    def cancel_journal_entry(self, name: str) -> None:
        self._repo.cancel_journal_entry(self._tid(), name)

    def restore_cancelled(self, name: str) -> None:
        """Restore a cancelled entry (docstatus 2 -> 1) directly."""
        self._repo.restore_cancelled(self._tid(), name)

    def set_status(self, name: str, docstatus: int, tenant: int | None = None) -> None:
        tid = tenant if tenant is not None else self._tid()
        self._repo.set_status(tid, name, docstatus)

    def delete_entry(self, name: str) -> None:
        """Delete an entry and its lines permanently — no ghost records."""
        self._repo.delete_entry(self._tid(), name)

    def entry_accounts(self, name: str) -> tuple[str, str] | None:
        return self._repo.entry_accounts(self._tid(), name)

    def entry_detail(self, name: str) -> dict | None:
        return self._repo.entry_detail(self._tid(), name)

    def entries_of_account(
        self,
        account: str,
        docstatus: tuple[int, ...] = (1,),
    ) -> list[str]:
        return self._repo.entries_of_account(self._tid(), account, docstatus=docstatus)

    def entry_counts(self, account_names: list[str]) -> dict[str, int]:
        return self._repo.entry_counts(self._tid(), account_names)

    def account_balance(self, account: str, on_date: date | None = None) -> Decimal:
        return self._repo.account_balance(self._tid(), account, on_date=on_date)

    def recent_entries(
        self,
        limit: int = 10,
        *,
        extra_filters: list | None = None,
        order_by: str = "posting_date desc, name desc",
        docstatus: tuple[int, ...] = (1,),
    ) -> list[dict]:
        return self._repo.recent_entries(
            self._tid(), limit=limit, extra_filters=extra_filters,
            order_by=order_by, docstatus=docstatus,
        )

    def find_entry(self, keywords: str, limit: int | None = None) -> dict | None:
        if limit is None:
            limit = self._constants.get("find_entry_limit")
        words = [w.lower() for w in keywords.split() if len(w) > 2]
        for r in self._repo.recent_entries(self._tid(), limit=limit):
            rem = (r.get("user_remark") or "").lower()
            if any(w in rem for w in words):
                return r
        return None

    # ----------------------------------------------------------------- integrity
    def assert_balanced(self, tenant: int | None = None) -> int:
        tid = tenant if tenant is not None else (self._tid() if self._has_tenant() else None)
        try:
            return self._repo.assert_balanced(tid)
        except UnbalancedEntriesError as e:
            raise LedgerError(
                glossary.t("error_unbalanced_entries", lang="ru").replace("{bad}", str(e.bad[:5]))
            )
        except GlobalImbalanceError as e:
            raise LedgerError(
                glossary.t("error_global_imbalance", lang="ru")
                .replace("{gd}", str(e.debit))
                .replace("{gc}", str(e.credit))
            )
