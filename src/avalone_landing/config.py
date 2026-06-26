"""Runtime configuration for avalone.online portal.

Ветки/приложения теперь живут в едином реестре avalone_core.registry.
Этот файл отвечает только за deployment-настройки (host, port, secrets).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVALONE_", env_file=".env", extra="ignore")

    web_base_url: str = "https://avalone.online"
    web_host: str = "127.0.0.1"
    web_port: int = 8811
    fernet_key: str = "change-me-in-production"


@lru_cache
def settings() -> Settings:
    return Settings()


# Единый реестр для импорта из портала.
from avalone_core.registry import AvaloneRegistry  # noqa: E402

__all__ = ["settings", "AvaloneRegistry"]
