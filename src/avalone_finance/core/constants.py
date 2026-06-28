"""Tunable instance constants — backward-compatible facade over ConstantsService.

Every hardcoded numeric/string threshold that affects runtime behaviour lives
here with a default. Admins can override any value via global_settings; the
override is read from DB on each call, so changes apply without restart.

Values are stored as TEXT in global_settings and coerced back to the type of
the default. If coercion fails, the default is used.

Реализация теперь живёт в ``avalone_finance.core.constants_service``. Этот
модуль сохраняет старый API на уровне констант/функций, пробрасывая вызовы в
дефолтный экземпляр ``ConstantsService``.
"""

from __future__ import annotations

from typing import Any

from avalone_finance.core.constants_service import (
    DEFAULTS,
    ConstantsService,
)

# Backward-compatible module-level constant.
DEFAULTS = DEFAULTS

_default_service: ConstantsService | None = None


def _service() -> ConstantsService:
    global _default_service
    if _default_service is None:
        _default_service = ConstantsService()
    return _default_service


def get(name: str) -> Any:
    """Return current effective value for a tunable constant."""
    return _service().get(name)


def all_effective() -> dict[str, Any]:
    """All constants with their current effective values."""
    return _service().all_effective()


# Re-export the service for callers that want to build their own instance.
__all__ = ["DEFAULTS", "get", "all_effective", "ConstantsService"]
