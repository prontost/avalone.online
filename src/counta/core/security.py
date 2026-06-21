"""Защита аутентификации: rate-limit и токены подтверждения почты.

Rate-limit — in-memory скользящее окно по ключу (ip|login). Достаточно для
одного процесса с --reload (single uvicorn). При горизонтальном масштабе
заменить на Redis. Цель — отбить брутфорс пароля и спам-регистрацию.

Email-токены: код в users.email_verify (через core/tenant), отправка письма —
core/notify._send_email. Здесь генерация/проверка кода и throttle.
"""

import secrets
import time
from collections import defaultdict, deque

from counta.core import constants

_hits: dict[str, deque] = defaultdict(deque)


def _allow(key: str, limit: int | None = None, window: int | None = None) -> bool:
    if limit is None:
        limit = 10
    if window is None:
        window = constants.get("rate_limit_window_sec")
    now = time.time()
    dq = _hits[key]
    while dq and dq[0] < now - window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def allow_login(ip: str, login: str) -> bool:
    return _allow(f"login:{ip}:{login.lower()}", constants.get("max_login_attempts"))


def allow_register(ip: str) -> bool:
    return _allow(f"reg:{ip}", constants.get("max_register_attempts"))


def allow_verify(ip: str) -> bool:
    return _allow(f"vrf:{ip}", constants.get("max_verify_attempts"))


def allow_recover(ip: str) -> bool:
    return _allow(f"rec:{ip}", constants.get("max_recover_attempts"))


def new_code() -> str:
    """6-значный код подтверждения почты."""
    return f"{secrets.randbelow(1_000_000):06d}"


def new_token() -> str:
    """Одноразовый токен сброса пароля (URL-safe)."""
    return secrets.token_urlsafe(constants.get("password_reset_token_entropy"))


def validate_password(password: str, strict: bool = False) -> tuple[bool, str]:
    """Validate password complexity. Returns (ok, error_message).

    Non-strict (default): only minimum length from constants.
    Strict: ≥8 chars, uppercase, lowercase, digit, special character.
    """
    import re
    if not password:
        return False, "Пароль не может быть пустым"
    min_len = constants.get("min_password_length")
    if not strict:
        if len(password) < min_len:
            return False, f"Пароль ≥{min_len} символов"
        return True, ""
    if len(password) < 8:
        return False, "Пароль ≥8 символов"
    if not re.search(r"[A-ZА-Я]", password):
        return False, "Пароль должен содержать заглавную букву"
    if not re.search(r"[a-zа-я]", password):
        return False, "Пароль должен содержать строчную букву"
    if not re.search(r"\d", password):
        return False, "Пароль должен содержать цифру"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        return False, "Пароль должен содержать спецсимвол"
    return True, ""
