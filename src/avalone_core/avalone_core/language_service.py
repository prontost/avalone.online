"""Language detection and persistence for the Avalone platform."""

from __future__ import annotations

from fastapi import Request
from itsdangerous import URLSafeSerializer

from avalone_core.database import Database, Service


class _CookieAuth:
    """Minimal auth helper that only reads the Avalone session cookie."""

    _COOKIE = "avalone_session"
    _SALT = "avalone-session"

    def __init__(self, secret_key: str = "") -> None:
        self._signer = URLSafeSerializer(secret_key or "change-me-in-production", salt=self._SALT)

    def user_id_of(self, request: Request) -> int:
        token = request.cookies.get(self._COOKIE)
        if not token:
            return 0
        try:
            return int(self._signer.loads(token))
        except Exception:
            return 0


class LanguageService(Service):
    """Detect, resolve and persist user language preference.

    Resolution order:
    1. Authenticated user's explicit `users.language` if not 'auto'.
    2. `avalone_lang` cookie (including 'auto').
    3. `Accept-Language` header mapped to supported language.
    4. Fallback 'ru'.
    """

    _db: Database
    _SUPPORTED = ("auto", "ru", "en", "ko")
    _LANG_ALIASES = {"ru": ("ru",), "en": ("en",), "ko": ("ko", "kr")}

    def __init__(self, auth_service=None, db: Database | None = None) -> None:
        super().__init__()
        self._auth = auth_service or _CookieAuth()
        self._db = db or Database.shared()

    @classmethod
    def supported(cls) -> list[str]:
        return list(cls._SUPPORTED)

    def detect(self, request: Request) -> str:
        cookie_lang = request.cookies.get("avalone_lang", "")
        resolved = self._normalize(cookie_lang)

        user_id = self._auth.user_id_of(request)
        if user_id:
            user_lang = self._get_user_language(user_id)
            if user_lang and user_lang != "auto":
                resolved = user_lang
            elif cookie_lang == "auto" or not cookie_lang:
                resolved = self._from_accept_language(
                    request.headers.get("accept-language", "")
                )
        else:
            if cookie_lang == "auto" or not cookie_lang:
                resolved = self._from_accept_language(
                    request.headers.get("accept-language", "")
                )

        return self._normalize(resolved)

    def set_user_language(self, user_id: int, lang: str) -> None:
        lang = self._normalize(lang)
        with self._db.connection() as con:
            con.execute("UPDATE users SET language = ? WHERE id = ?", (lang, user_id))
            con.commit()

    def _get_user_language(self, user_id: int) -> str:
        with self._db.connection() as con:
            row = con.execute("SELECT language FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["language"] if row else "auto"

    def _normalize(self, lang: str) -> str:
        lang = (lang or "").strip().lower()
        if lang in self._SUPPORTED:
            return lang
        return "auto"

    def _from_accept_language(self, header: str) -> str:
        if not header:
            return "ru"
        for part in header.split(","):
            tag = part.split(";")[0].strip().lower()
            if not tag:
                continue
            for lang, aliases in self._LANG_ALIASES.items():
                if any(tag.startswith(a) for a in aliases):
                    return lang
        return "ru"
