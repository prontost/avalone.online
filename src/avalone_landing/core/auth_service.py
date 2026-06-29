"""Signed multi-session cookie handling for the Avalone portal."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request, Response
from itsdangerous import URLSafeSerializer

from avalone_core.database import Service

from avalone_landing.config import Settings, settings


class AuthService(Service):
    """Signs, verifies and clears the `avalone_sessions` cookie.

    The cookie stores a signed JSON object:
        {"active": 123, "sessions": [{"uid": 123, "at": "..."}, ...]}

    This allows multiple accounts to be signed in at once (like Google)
    while only one is active per request.
    """

    SESSION_COOKIE = "avalone_sessions"
    LEGACY_COOKIE = "avalone_session"
    SESSION_MAX_AGE_DAYS = 90
    SALT = "avalone-session"

    def __init__(self, cfg: Settings | None = None) -> None:
        self._cfg = cfg or settings()
        self._signer = URLSafeSerializer(self._cfg.fernet_key, salt=self.SALT)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _parse(self, token: str | None) -> tuple[int, list[dict[str, Any]]]:
        """Return (active_user_id, sessions)."""
        if not token:
            return 0, []
        try:
            data = self._signer.loads(token)
        except Exception:
            return 0, []

        # Legacy single-session cookie was a signed user id.
        if isinstance(data, int):
            return data, [{"uid": data, "at": self._now()}]
        if isinstance(data, str):
            try:
                uid = int(data)
                return uid, [{"uid": uid, "at": self._now()}]
            except Exception:
                return 0, []

        if isinstance(data, dict):
            active = data.get("active") or 0
            sessions = data.get("sessions") or []
            cleaned = [
                {"uid": int(s["uid"]), "at": str(s.get("at") or self._now())}
                for s in sessions
                if isinstance(s, dict) and s.get("uid")
            ]
            return active, cleaned

        return 0, []

    def active_user_id(self, request: Request) -> int:
        active, _ = self._parse(request.cookies.get(self.SESSION_COOKIE))
        if active:
            return active
        # Fallback to legacy cookie and migrate on next issue.
        legacy = request.cookies.get(self.LEGACY_COOKIE)
        if legacy:
            try:
                return int(self._signer.loads(legacy))
            except Exception:
                pass
        return 0

    # Alias used by the shared ShellContextBuilder / LanguageService.
    user_id_of = active_user_id

    def session_uids(self, request: Request) -> list[int]:
        """Return signed-in user ids ordered by login time (oldest first)."""
        _, sessions = self._parse(request.cookies.get(self.SESSION_COOKIE))
        return [s["uid"] for s in sorted(sessions, key=lambda s: s["at"])]

    def cookie_domain(self, request: Request) -> str | None:
        host = request.url.hostname or ""
        if host in ("localhost", "127.0.0.1"):
            return None
        return ".avalone.online"

    def _use_secure_cookie(self, request: Request) -> bool:
        # Only mark the cookie Secure when the request itself arrived over HTTPS.
        # This keeps localhost/HTTP development working and lets TestClient see
        # the cookie without having to fake TLS.
        return request.url.scheme == "https"

    def _set_cookie(self, request: Request, response: Response, active: int, sessions: list[dict[str, Any]]) -> None:
        value = {"active": active, "sessions": sessions}
        # SameSite=None is only needed for true cross-site flows. Lax is safer
        # for same-site navigation and avoids Safari/third-party cookie blocks.
        secure = self._use_secure_cookie(request)
        response.set_cookie(
            self.SESSION_COOKIE,
            self._signer.dumps(value),
            httponly=True,
            secure=secure,
            samesite="lax",
            domain=self.cookie_domain(request),
            max_age=60 * 60 * 24 * self.SESSION_MAX_AGE_DAYS,
        )
        # Clear legacy cookie if present.
        if self.LEGACY_COOKIE in request.cookies:
            response.delete_cookie(
                self.LEGACY_COOKIE,
                domain=self.cookie_domain(request),
                path="/",
                samesite="lax",
                secure=secure,
                httponly=True,
            )

    def issue_session(self, request: Request, response: Response, user_id: int) -> None:
        active, sessions = self._parse(request.cookies.get(self.SESSION_COOKIE))
        sessions = [s for s in sessions if s["uid"] != user_id]
        sessions.append({"uid": user_id, "at": self._now()})
        self._set_cookie(request, response, user_id, sessions)

    def switch_active(self, request: Request, response: Response, user_id: int) -> bool:
        active, sessions = self._parse(request.cookies.get(self.SESSION_COOKIE))
        if not any(s["uid"] == user_id for s in sessions):
            return False
        self._set_cookie(request, response, user_id, sessions)
        return True

    def clear_active_session(self, request: Request, response: Response) -> int:
        """Remove the active session. Activate the oldest remaining one.

        Returns the new active user id or 0 if no sessions remain.
        """
        active, sessions = self._parse(request.cookies.get(self.SESSION_COOKIE))
        sessions = [s for s in sessions if s["uid"] != active]
        if sessions:
            new_active = sessions[0]["uid"]
            self._set_cookie(request, response, new_active, sessions)
            return new_active
        self.clear_all_sessions(request, response)
        return 0

    def clear_all_sessions(self, request: Request, response: Response) -> None:
        response.delete_cookie(
            self.SESSION_COOKIE,
            domain=self.cookie_domain(request),
            path="/",
            samesite="none",
            secure=True,
            httponly=True,
        )
        if self.LEGACY_COOKIE in request.cookies:
            response.delete_cookie(
                self.LEGACY_COOKIE,
                domain=self.cookie_domain(request),
                path="/",
                samesite="none",
                secure=True,
                httponly=True,
            )
