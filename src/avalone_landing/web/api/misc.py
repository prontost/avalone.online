"""Miscellaneous portal JSON API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from avalone_core.device_service import DeviceService
from avalone_core.language_service import LanguageService
from avalone_core.referral_service import ReferralService
from avalone_landing.core.models import User
from avalone_landing.web.dependencies import current_user

router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


@router.post("/api/lang")
async def set_language(request: Request, user: User | None = Depends(current_user)):
    body = await request.json()
    lang = str(body.get("lang", "auto")).strip().lower()
    service = LanguageService()
    service.detect(request)  # warm resolution
    resolved = service._normalize(lang)

    if user is not None:
        service.set_user_language(user.id, resolved)

    response = JSONResponse({"ok": True, "lang": resolved})
    response.set_cookie(
        "avalone_lang",
        resolved,
        max_age=60 * 60 * 24 * 365,
        path="/",
        samesite="lax",
        secure=True,
    )
    return response


@router.get("/api/referral/code")
async def referral_code(user: User | None = Depends(current_user)):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    code = ReferralService().get_or_create_code(user.id)
    return {"code": code, "url": f"https://avalone.online?ref={code}"}


@router.get("/api/referral/stats")
async def referral_stats(user: User | None = Depends(current_user)):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return ReferralService().stats(user.id)


@router.post("/api/heartbeat")
async def heartbeat(request: Request, user: User | None = Depends(current_user)):
    if user is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    device_id = str(body.get("device_id", "")).strip() or None
    screen = str(body.get("screen", "")).strip()
    platform = str(body.get("platform", "")).strip()
    seconds = body.get("seconds", 5)
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = 5
    user_agent = request.headers.get("user-agent", "")
    result = DeviceService().heartbeat(
        user.id,
        device_id,
        user_agent,
        screen,
        platform,
        _client_ip(request),
        seconds,
    )
    return result
