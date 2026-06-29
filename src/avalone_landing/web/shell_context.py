"""Shared shell rendering helper for Avalone portal pages.

The actual shell context logic lives in ``avalone_core.ui.shell_context`` so that
the portal and every mounted module render an identical shell. This module only
provides a thin, portal-specific wrapper with the correct base URL and defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from avalone_core.ui.shell_context import ShellContextBuilder

from avalone_landing.config import Settings, settings
from avalone_landing.core.auth_service import AuthService
from avalone_landing.core.user_service import UserService


@dataclass
class ShellContext:
    """Portal-facing wrapper around the unified ``ShellContextBuilder``.

    Dependencies are injected via the constructor so routes receive a ready
    instance through FastAPI ``Depends``.
    """

    auth_service: AuthService
    user_service: UserService
    cfg: Settings

    def build(
        self,
        templates: Jinja2Templates,
        request: Request,
        current_app: str = "portal",
        app_nav: list[dict] | None = None,
        build_id: str = "",
        **extra: object,
    ) -> dict:
        """Return the context dict used by shell-based templates."""
        builder = ShellContextBuilder(
            auth_provider=self.auth_service,
            user_service=self.user_service,
            templates=templates,
            portal_url=self.cfg.web_base_url,
            current_app=current_app,
            build_id=build_id,
            app_nav=app_nav or [],
        )
        ctx = builder.build(request)
        ctx.update(extra)
        return ctx


def render_shell_context(
    templates: Jinja2Templates,
    request: Request,
    current_app: str = "portal",
    app_nav: list[dict] | None = None,
    build_id: str = "",
    **extra: object,
) -> dict:
    """Backward-compatible wrapper. Prefer injecting ``ShellContext``."""
    builder = ShellContext(
        auth_service=AuthService(),
        user_service=UserService(),
        cfg=settings(),
    )
    return builder.build(
        templates,
        request,
        current_app=current_app,
        app_nav=app_nav,
        build_id=build_id,
        **extra,
    )
