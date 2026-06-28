"""Защита аутентификации: rate-limit и токены подтверждения почты.

Rate-limit — in-memory скользящее окно по ключу (ip|login). Достаточно для
одного процесса с --reload (single uvicorn). При горизонтальном масштабе
заменить на Redis. Цель — отбить брутфорс пароля и спам-регистрацию.

Email-токены: код в users.email_verify (через core/tenant), отправка письма —
core/notify._send_email. Здесь генерация/проверка кода и throttle.

Бизнес-логика живёт в :class:`SecurityService`. Модуль-уровень — тонкий
фасад над дефолтным экземпляром.
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from typing import Any

from avalone_finance.core.constants_service import ConstantsService


class SecurityService:
    """Аутентификационная защита: rate-limit, коды, токены, проверка пароля."""

    def __init__(
        self,
        constants_service: ConstantsService | None = None,
        glossary_service: Any | None = None,
    ) -> None:
        self._constants_service = constants_service
        self._glossary_service = glossary_service
        self._hits: dict[str, deque] = defaultdict(deque)

    def _constants(self) -> ConstantsService:
        if self._constants_service is None:
            self._constants_service = ConstantsService()
        return self._constants_service

    def _glossary(self) -> Any:
        if self._glossary_service is None:
            from avalone_core import glossary_db as _glossary_module
            self._glossary_service = _glossary_module
        return self._glossary_service

    def _translate(self, key: str, lang: str) -> str:
        svc = self._glossary()
        if hasattr(svc, "t"):
            return svc.t(key, lang=lang)
        return svc.translate(key, lang)

    def _allow(
        self,
        key: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> bool:
        if limit is None:
            limit = 10
        if window is None:
            window = self._constants().get("rate_limit_window_sec")
        now = time.time()
        dq = self._hits[key]
        while dq and dq[0] < now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def allow_login(self, ip: str, login: str) -> bool:
        return self._allow(
            f"login:{ip}:{login.lower()}",
            self._constants().get("max_login_attempts"),
        )

    def allow_register(self, ip: str) -> bool:
        return self._allow(
            f"reg:{ip}",
            self._constants().get("max_register_attempts"),
        )

    def allow_verify(self, ip: str) -> bool:
        return self._allow(
            f"vrf:{ip}",
            self._constants().get("max_verify_attempts"),
        )

    def allow_recover(self, ip: str) -> bool:
        return self._allow(
            f"rec:{ip}",
            self._constants().get("max_recover_attempts"),
        )

    def new_code(self) -> str:
        """6-значный код подтверждения почты."""
        return f"{secrets.randbelow(1_000_000):06d}"

    def new_token(self) -> str:
        """Одноразовый токен сброса пароля (URL-safe)."""
        return secrets.token_urlsafe(
            self._constants().get("password_reset_token_entropy")
        )

    def validate_password(
        self,
        password: str,
        strict: bool = False,
        lang: str = "ru",
    ) -> tuple[bool, str]:
        """Validate password complexity. Returns (ok, error_message_key).

        Non-strict (default): only minimum length from constants.
        Strict: ≥8 chars, uppercase, lowercase, digit, special character.
        """
        import re
        if not password:
            return False, self._translate("error_password_empty", lang)
        min_len = self._constants().get("min_password_length")
        if not strict:
            if len(password) < min_len:
                msg = self._translate("error_password_min_len", lang).replace(
                    "{min_len}", str(min_len)
                )
                return False, msg
            return True, ""
        if len(password) < 8:
            return False, self._translate("error_password_min_len", lang).replace(
                "{min_len}", "8"
            )
        if not re.search(r"[A-ZА-Я]", password):
            return False, self._translate(
                "error_password_complexity_upper", lang
            )
        if not re.search(r"[a-zа-я]", password):
            return False, self._translate(
                "error_password_complexity_lower", lang
            )
        if not re.search(r"\d", password):
            return False, self._translate(
                "error_password_complexity_digit", lang
            )
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
            return False, self._translate(
                "error_password_complexity_special", lang
            )
        return True, ""


# --------------------------------------------------------------------------- #
# Backward-compatible module-level facade
_default_service: SecurityService | None = None


def _service() -> SecurityService:
    global _default_service
    if _default_service is None:
        _default_service = SecurityService()
    return _default_service


def _allow(
    key: str,
    limit: int | None = None,
    window: int | None = None,
) -> bool:
    return _service()._allow(key, limit, window)


def allow_login(ip: str, login: str) -> bool:
    return _service().allow_login(ip, login)


def allow_register(ip: str) -> bool:
    return _service().allow_register(ip)


def allow_verify(ip: str) -> bool:
    return _service().allow_verify(ip)


def allow_recover(ip: str) -> bool:
    return _service().allow_recover(ip)


def new_code() -> str:
    return _service().new_code()


def new_token() -> str:
    return _service().new_token()


def validate_password(
    password: str,
    strict: bool = False,
    lang: str = "ru",
) -> tuple[bool, str]:
    return _service().validate_password(password, strict, lang)


__all__ = [
    "SecurityService",
    "allow_login",
    "allow_register",
    "allow_verify",
    "allow_recover",
    "new_code",
    "new_token",
    "validate_password",
]
