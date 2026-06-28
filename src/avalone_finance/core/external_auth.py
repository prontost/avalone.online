"""Avalone SSO integration: shared signed cookie across avalone.online domain.

The landing app issues ``avalone_sessions`` cookie (signed JSON with active user
and a list of signed-in accounts). The finance module reads it, verifies the
signature with the shared key, and returns the Avalone user_id. The user_id IS
the finance ``tenant_id``; no local mapping table is needed.
"""

from __future__ import annotations

from fastapi import Request
from itsdangerous import URLSafeSerializer

from avalone_finance.core.config import settings


class FinanceAuthProvider:
    """Reads the Avalone portal session cookie and returns the active user id."""

    _NEW_COOKIE = "avalone_sessions"
    _LEGACY_COOKIE = "avalone_session"
    _SALT = "avalone-session"

    def __init__(self, secret_key: str | None = None) -> None:
        key = secret_key or settings().avalone_fernet_key or settings().fernet_key
        self._signer = URLSafeSerializer(key, salt=self._SALT)

    def user_id_of(self, request: Request) -> int:
        """Return Avalone user_id from cookie, or 0 if missing/invalid."""
        token = request.cookies.get(self._NEW_COOKIE)
        if token:
            try:
                return self._active_uid_from_data(self._signer.loads(token))
            except Exception:
                pass
        # Fallback to legacy single-session cookie.
        token = request.cookies.get(self._LEGACY_COOKIE)
        if token:
            try:
                return self._active_uid_from_data(self._signer.loads(token))
            except Exception:
                pass
        return 0

    @staticmethod
    def _active_uid_from_data(data) -> int:
        if isinstance(data, int):
            return data
        if isinstance(data, str):
            try:
                return int(data)
            except Exception:
                return 0
        if isinstance(data, dict):
            return data.get("active") or 0
        return 0


# Backward-compatible module-level helper used by tests and older code.
def user_id_of(request: Request) -> int:
    return FinanceAuthProvider().user_id_of(request)
