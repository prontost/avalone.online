"""Single source of truth for the Avalone application shell context.

Both the portal and mounted modules (finance, etc.) must render the shell with
identical user/session/language data. This builder is the only place that decides
what goes into the shell, so pages cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from avalone_core.language_service import LanguageService
from avalone_core.registry import AvaloneRegistry
from avalone_core.ui.widgets import AuthModal, Shell


def _user_attr(user: Any, name: str) -> Any:
    """Read an attribute from either a dataclass/model or a plain dict."""
    if isinstance(user, dict):
        return user.get(name)
    return getattr(user, name, None)


class _AuthProvider(Protocol):
    def active_user_id(self, request: Request) -> int: ...
    def session_uids(self, request: Request) -> list[int]: ...


class _UserService(Protocol):
    def get_user(self, user_id: int) -> Any | None: ...


@dataclass
class ShellContextBuilder:
    """Build the shared shell context for any Avalone app or module.

    The builder receives an auth provider and a user service. It resolves the
    active user, all signed-in sessions, language and app branches, then renders
    the shell HTML. Route handlers only add their own page-specific data on top.
    """

    auth_provider: _AuthProvider
    user_service: _UserService
    templates: Jinja2Templates
    portal_url: str = "/"
    current_app: str = "portal"
    build_id: str = ""
    app_nav: list[dict[str, Any]] = field(default_factory=list)
    breadcrumbs: list[dict[str, Any]] = field(default_factory=list)
    notifications_count: int = 0

    def build(self, request: Request) -> dict[str, Any]:
        env = self.templates.env
        lang = LanguageService(auth_service=self.auth_provider).detect(request)
        branches = AvaloneRegistry.for_shell(lang)

        active_uid = self.auth_provider.active_user_id(request)
        user = self.user_service.get_user(active_uid) if active_uid else None

        sessions: list[dict[str, Any]] = []
        for uid in self.auth_provider.session_uids(request):
            u = self.user_service.get_user(uid)
            if u:
                sessions.append(
                    {
                        "id": _user_attr(u, "id"),
                        "login": _user_attr(u, "login"),
                        "name": (_user_attr(u, "name") or ""),
                        "email": (_user_attr(u, "email") or ""),
                        "active": uid == active_uid,
                    }
                )

        auth_mode = request.query_params.get("mode") or "login"
        if auth_mode not in ("login", "register", "forgot", "reset"):
            auth_mode = "login"
        auth_token = request.query_params.get("token", "")
        auth_modal = AuthModal(
            mode=auth_mode, token=auth_token, user=user, lang=lang
        )
        auth_modal_html = auth_modal.render(env, request)

        shell = Shell(
            current_app=self.current_app,
            user=user,
            sessions=sessions,
            auth_modal_html=auth_modal_html,
            branches=branches,
            app_nav=self.app_nav,
            breadcrumbs=self.breadcrumbs,
            notifications_count=self.notifications_count,
            lang=lang,
            portal_url=self.portal_url,
        )

        return {
            "build_id": self.build_id,
            "user": user,
            "lang": lang,
            "sessions": sessions,
            "shell_html": shell.render(env, request),
        }
