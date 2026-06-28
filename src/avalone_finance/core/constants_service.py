"""Tunable instance constants as a dependency-injectable service.

This module extracts the logic previously in ``avalone_finance.core.constants``
into a class so callers can provide a custom ``GlobalSettingsService`` while
keeping the old module-level API working through the facade in ``constants.py``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from avalone_finance.core.global_settings_service import GlobalSettingsService

DEFAULTS: dict[str, Any] = {
    # --- security / auth ---
    "rate_limit_window_sec": 300,
    "max_login_attempts": 8,
    "max_register_attempts": 5,
    "max_verify_attempts": 10,
    "max_recover_attempts": 5,
    "min_login_length": 3,
    "min_password_length": 6,
    "session_max_age_days": 90,
    "accounts_max_age_days": 90,
    "password_reset_token_entropy": 32,  # secrets.token_urlsafe(n)

    # --- ledger / UX ---
    "recent_entries_limit": 200,
    "export_entries_limit": 10_000,
    "find_entry_limit": 30,

    # --- logging ---
    "log_max_bytes": 5 * 1024 * 1024,
    "log_backup_count": 3,

    # --- misc ---
    "qr_default_size": 200,
    "build_id_hash_length": 12,
}


class ConstantsService:
    """Tunable constants with optional ``GlobalSettingsService`` override."""

    DEFAULTS = DEFAULTS

    def __init__(self, global_settings_service: GlobalSettingsService | None = None) -> None:
        self._global_settings = global_settings_service

    def _settings_service(self):
        if self._global_settings is not None:
            return self._global_settings
        from avalone_finance.core.global_settings_service import GlobalSettingsService
        return GlobalSettingsService()

    def _coerce(self, name: str, raw: str) -> Any:
        default = self.DEFAULTS[name]
        try:
            if isinstance(default, bool):
                return raw.lower() in ("1", "true", "yes", "on")
            if isinstance(default, int):
                return int(raw)
            if isinstance(default, float):
                return float(raw)
            if isinstance(default, Decimal):
                return Decimal(raw)
            return raw
        except Exception:
            return default

    def get(self, name: str) -> Any:
        """Return current effective value for a tunable constant."""
        if name not in self.DEFAULTS:
            raise KeyError(f"unknown constant: {name}")
        override = self._settings_service().get(name)
        if override is None:
            return self.DEFAULTS[name]
        return self._coerce(name, override)

    def all_effective(self) -> dict[str, Any]:
        """All constants with their current effective values."""
        return {name: self.get(name) for name in self.DEFAULTS}
