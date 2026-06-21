from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration comes from COUNTA_* env vars (or .env for dev)."""

    model_config = SettingsConfigDict(env_prefix="COUNTA_", env_file=".env", extra="ignore")

    # Движок книги — наш SQLite-леджер в counta.db (core/sqlledger). ERPNext и
    # Telegram-бот удалены 2026-06-16 (Counta = чистый PWA на SQLite).

    # Подпись session-cookie (+ шифрование секретов, если понадобится)
    fernet_key: str
    web_base_url: str = "https://counta.avalone.online"
    web_host: str = "127.0.0.1"
    web_port: int = 8810

    # PWA login (personal phase: один пароль; мультиюзер — отдельная итерация)
    web_password: str = ""
    # Регистрация: "open" — любой создаёт аккаунт; "invite" — только с кодом
    # приглашения (registration_invite_code); "closed" — регистрация отключена.
    registration_mode: str = "open"
    registration_invite_code: str = ""

    # Строгая политика паролей: если true, пароль должен быть ≥8 символов и
    # содержать заглавную/строчную букву, цифру и спецсимвол.
    strict_password_policy: bool = False

    # e-mail канал уведомлений (опционально; без ключей работает только история)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""        # Gmail-логин для SMTP
    smtp_password: str = ""    # Gmail App Password
    smtp_from: str = ""        # адрес в From (send-as), напр. noreply@avalone.online


@lru_cache
def settings() -> Settings:
    return Settings()


def registration_mode() -> str:
    """Runtime registration mode: DB overrides env. Owner can flip it from UI."""
    try:
        from counta.core import global_settings
        db_val = global_settings.get("registration_mode")
        if db_val and db_val.strip().lower() in ("open", "invite", "closed"):
            return db_val.strip().lower()
    except Exception:
        pass
    return settings().registration_mode


def registration_invite_code() -> str:
    """Invite code: DB overrides env so owner can rotate it without restart."""
    try:
        from counta.core import global_settings
        db_val = global_settings.get("registration_invite_code")
        if db_val is not None:
            return db_val
    except Exception:
        pass
    return settings().registration_invite_code


def strict_password_policy() -> bool:
    """Runtime toggle for strict password complexity. DB overrides env."""
    try:
        from counta.core import global_settings
        db_val = global_settings.get("strict_password_policy")
        if db_val is not None:
            return db_val.strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        pass
    return settings().strict_password_policy


def _runtime(key: str, default: str) -> str:
    """Read a runtime setting from DB first, then env default."""
    try:
        from counta.core import global_settings
        db_val = global_settings.get(key)
        if db_val is not None:
            return db_val
    except Exception:
        pass
    return default


def default_currency() -> str:
    from counta.core import money
    return _runtime("default_currency", money.DEFAULT_CURRENCY)


def web_base_url() -> str:
    return _runtime("web_base_url", settings().web_base_url)
