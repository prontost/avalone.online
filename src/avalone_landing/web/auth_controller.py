"""Auth controller for the Avalone portal.

Centralises validation and business flow for sign-in, sign-up and password
reset. Route handlers remain thin and only choose the response format
(HTML, JSON or redirect).
"""

from __future__ import annotations

from dataclasses import dataclass

from avalone_landing.config import Settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.mail_service import MailService
from avalone_landing.core.models import User
from avalone_landing.core.user_service import UserService


@dataclass(frozen=True)
class AuthResult:
    success: bool
    user_id: int | None = None
    user: User | None = None
    error: str = ""
    error_code: int = 400
    already_active: bool = False
    reset_url: str = ""
    next_url: str = "/"


class AuthController:
    """Class-based entry point for authentication flows."""

    _MIN_PASSWORD_LENGTH = 6

    def __init__(
        self,
        auth_service: AuthService,
        user_service: UserService,
        mail_service: MailService,
        cfg: Settings,
    ) -> None:
        self._auth = auth_service
        self._users = user_service
        self._mail = mail_service
        self._cfg = cfg

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, login: str, password: str, active_user_id: int = 0) -> AuthResult:
        login = login.strip().lower()
        if not login or not password:
            return AuthResult(success=False, error="auth_error_required")
        user = self._users.authenticate(login, password)
        if not user:
            return AuthResult(success=False, error="auth_error_invalid_credentials", error_code=401)
        if user.id == active_user_id:
            return AuthResult(success=False, error="auth_already_active", already_active=True)
        return AuthResult(success=True, user_id=user.id, user=user)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        login: str,
        password: str,
        password2: str,
        invite: str = "",
        active_user_id: int = 0,
    ) -> AuthResult:
        login = login.strip().lower()
        error = self._registration_error(login, password, password2)
        if error:
            return AuthResult(success=False, error=error)
        try:
            user_id = self._users.create_user(login, password, referral_code=invite)
        except ValueError as exc:
            return AuthResult(success=False, error=str(exc))
        return AuthResult(success=True, user_id=user_id)

    def _registration_error(self, login: str, password: str, password2: str) -> str:
        if not login or not password:
            return "auth_error_required"
        if password != password2:
            return "auth_error_password_mismatch"
        if len(password) < self._MIN_PASSWORD_LENGTH:
            return "auth_error_password_too_short"
        if self._users.login_taken(login):
            return "auth_error_login_taken"
        return ""

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    def request_password_reset(self, login_or_email: str) -> AuthResult:
        login_or_email = login_or_email.strip()
        if not login_or_email:
            return AuthResult(success=False, error="reset_error_required")
        result = self._users.request_password_reset(login_or_email)
        reset_url = ""
        if result:
            user, token = result
            if user.email:
                reset_url = f"{self._cfg.web_base_url}/login?mode=reset&token={token}"
                subject = self._t("reset_email_subject")
                body = self._t("reset_email_body").format(login=user.login, url=reset_url)
                try:
                    self._mail.send_email(user.email, subject, body)
                except Exception:
                    pass
        return AuthResult(success=True, reset_url=reset_url)

    def reset_password(self, token: str, password: str, password2: str) -> AuthResult:
        user = self._users.get_user_by_reset_token(token) if token else None
        if not user:
            return AuthResult(success=False, error="reset_token_invalid")
        error = self._password_change_error(password, password2)
        if error:
            return AuthResult(success=False, error=error)
        try:
            user = self._users.reset_password(token, password)
        except ValueError as exc:
            return AuthResult(success=False, error=str(exc))
        if user is None:
            return AuthResult(success=False, error="reset_token_invalid")
        return AuthResult(success=True, user_id=user.id, user=user)

    def _password_change_error(self, password: str, password2: str) -> str:
        if not password:
            return "auth_error_required"
        if password != password2:
            return "auth_error_password_mismatch"
        if len(password) < self._MIN_PASSWORD_LENGTH:
            return "auth_error_password_too_short"
        return ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def active_user_id(self, request) -> int:
        return self._auth.active_user_id(request)

    def issue_session(self, request, response, user_id: int) -> None:
        self._auth.issue_session(request, response, user_id)

    def _t(self, key: str) -> str:
        from avalone_core import glossary_db as glossary

        return glossary.t(key)
