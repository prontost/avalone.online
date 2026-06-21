"""Admin / instance management endpoints."""

import asyncio
import logging
import os
import signal
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from counta.core import app_access, config, constants, currency, db, global_settings, money, security, tenant
from counta.web.api.dependencies import require_admin

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")


@router.get("/settings")
async def admin_settings(admin_id: int = Depends(require_admin)):
    """Admins: current global settings like registration mode."""
    del admin_id
    return {
        "registration_mode": config.registration_mode(),
        "registration_invite_code": config.registration_invite_code(),
        "strict_password_policy": config.strict_password_policy(),
    }


@router.post("/settings")
async def admin_settings_update(payload: dict, admin_id: int = Depends(require_admin)):
    """Admins: update global settings."""
    del admin_id
    allowed = {"registration_mode", "registration_invite_code", "strict_password_policy"}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "registration_mode" and value not in ("open", "invite", "closed"):
            return JSONResponse({"error": "invalid_mode"}, status_code=400)
        if key == "strict_password_policy":
            value = "true" if str(value).strip().lower() in ("1", "true", "yes", "on") else "false"
        global_settings.set(key, str(value))
    return {
        "registration_mode": config.registration_mode(),
        "registration_invite_code": config.registration_invite_code(),
        "strict_password_policy": config.strict_password_policy(),
    }


@router.get("/users")
async def admin_users(admin_id: int = Depends(require_admin)):
    """Admins: list all users with entry counts and app access."""
    del admin_id
    with tenant._conn() as con:
        rows = con.execute(
            "SELECT u.id, u.login, u.email, u.email_verified, u.created_at, "
            "(SELECT COUNT(*) FROM led_entries e WHERE e.tenant=u.id) as entries "
            "FROM users u ORDER BY u.id"
        ).fetchall()
    return {
        "users": [
            {
                "id": r[0],
                "login": r[1],
                "email": r[2],
                "email_verified": bool(r[3]),
                "created_at": r[4],
                "entries": r[5],
                "apps": app_access.list_for_admin(r[0]),
            }
            for r in rows
        ]
    }


@router.get("/stats")
async def admin_stats(admin_id: int = Depends(require_admin)):
    """Admins: instance-wide stats."""
    del admin_id
    from counta.web.app import BUILD_ID
    db_size = db.DB_PATH.stat().st_size if db.DB_PATH.exists() else 0
    users = tenant._conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]
    entries = tenant._conn().execute("SELECT COUNT(*) FROM led_entries").fetchone()[0]
    currencies = len(currency.ALL)
    return {
        "build_id": BUILD_ID,
        "db_path": str(db.DB_PATH),
        "db_size": db_size,
        "users": users,
        "entries": entries,
        "currencies": currencies,
    }


@router.get("/health")
async def admin_health(admin_id: int = Depends(require_admin)):
    """Admins: basic health checks."""
    del admin_id
    db_ok = False
    try:
        with tenant._conn() as con:
            con.execute("SELECT 1")
        db_ok = True
    except Exception:
        log.exception("admin health db check failed")
    return {"db_ok": db_ok, "db_path": str(db.DB_PATH)}


@router.get("/admins")
async def admin_list(admin_id: int = Depends(require_admin)):
    """Admins: list current admins."""
    del admin_id
    return {"admins": tenant.list_admins()}


@router.get("/constants")
async def admin_constants_list(admin_id: int = Depends(require_admin)):
    """Admins: all tunable constants with current values and defaults."""
    del admin_id
    return {
        "constants": [
            {"key": k, "value": constants.get(k), "default": v, "type": type(v).__name__}
            for k, v in constants.DEFAULTS.items()
        ],
    }


@router.post("/constants")
async def admin_constants_update(payload: dict, admin_id: int = Depends(require_admin)):
    """Admins: update one or more tunable constants."""
    del admin_id
    updates = payload.get("updates", {})
    for key, value in updates.items():
        if key not in constants.DEFAULTS:
            return JSONResponse({"error": f"unknown_constant: {key}"}, status_code=400)
        default = constants.DEFAULTS[key]
        try:
            if isinstance(default, bool):
                str(value).lower() in ("1", "true", "yes", "on")
            elif isinstance(default, int):
                int(value)
            elif isinstance(default, float):
                float(value)
            elif isinstance(default, Decimal):
                Decimal(value)
        except Exception:
            return JSONResponse({"error": f"invalid_value: {key}"}, status_code=400)
        global_settings.set(key, str(value))
    return {"ok": True, "constants": constants.all_effective()}


@router.post("/admins")
async def admin_add(payload: dict, admin_id: int = Depends(require_admin)):
    """Admins: add a user as admin by login."""
    del admin_id
    login = (payload.get("login") or "").strip().lower()
    u = tenant.get_user_by_login(login)
    if not u:
        return JSONResponse({"error": "user_not_found"}, status_code=404)
    tenant.add_admin(u["id"])
    return {"ok": True, "id": u["id"], "login": u["login"]}


@router.delete("/admins/{user_id}")
async def admin_remove(user_id: int, admin_id: int = Depends(require_admin)):
    """Admins: remove admin rights."""
    del admin_id
    tenant.remove_admin(user_id)
    return {"ok": True}


@router.get("/config")
async def admin_config(admin_id: int = Depends(require_admin)):
    """Admins: editable runtime config + env secrets (masked) + static constants."""
    del admin_id
    from counta.web.app import COOKIE
    s = config.settings()

    def _mask(v: str | None) -> str:
        v = v or ""
        if len(v) <= 4:
            return "*" * len(v) or "—"
        return v[:2] + "****" + v[-2:]

    return {
        "runtime": {
            "registration_mode": config.registration_mode(),
            "registration_invite_code": config.registration_invite_code(),
            "strict_password_policy": config.strict_password_policy(),
            "default_currency": config.default_currency(),
            "web_base_url": config.web_base_url(),
        },
        "static": {
            "OWNER_TENANT_ID": tenant.OWNER_TENANT_ID,
            "DEFAULT_CURRENCY": money.DEFAULT_CURRENCY,
            "COOKIE_NAME": COOKIE,
            "registration_mode_env": s.registration_mode,
            "registration_invite_code_env": bool(s.registration_invite_code),
            "currencies_count": len(currency.ALL),
        },
        "env": {
            "smtp_password": _mask(s.smtp_password),
            "fernet_key": _mask(s.fernet_key),
            "web_host": s.web_host,
            "web_port": s.web_port,
            "smtp_host": s.smtp_host,
            "smtp_port": s.smtp_port,
            "smtp_user": s.smtp_user,
            "smtp_from": s.smtp_from,
        },
        "options": {
            "currencies": sorted(currency.ALL.keys()),
            "registration_modes": ["open", "invite", "closed"],
            "default_currencies": sorted(currency.ALL.keys()),
        },
    }


@router.post("/config")
async def admin_config_update(payload: dict, admin_id: int = Depends(require_admin)):
    """Admins: update runtime config keys stored in global_settings."""
    del admin_id
    allowed = {
        "registration_mode", "registration_invite_code", "strict_password_policy",
        "default_currency", "web_base_url",
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "registration_mode" and value not in ("open", "invite", "closed"):
            return JSONResponse({"error": "invalid_mode"}, status_code=400)
        if key == "default_currency" and value not in currency.ALL:
            return JSONResponse({"error": "invalid_currency"}, status_code=400)
        if key == "strict_password_policy":
            value = "true" if str(value).strip().lower() in ("1", "true", "yes", "on") else "false"
        global_settings.set(key, str(value))
    return {
        "ok": True,
        "registration_mode": config.registration_mode(),
        "registration_invite_code": config.registration_invite_code(),
        "strict_password_policy": config.strict_password_policy(),
        "default_currency": config.default_currency(),
        "web_base_url": config.web_base_url(),
    }


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: int, admin_id: int = Depends(require_admin)):
    """Admins: generate a one-time password reset link for a user."""
    from datetime import datetime, timedelta, timezone
    if user_id == admin_id:
        return JSONResponse({"error": "cannot_reset_self"}, status_code=400)
    u = tenant.get_user(user_id)
    if not u:
        return JSONResponse({"error": "user_not_found"}, status_code=404)
    token = security.new_token()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
    tenant.set_reset_token(user_id, token, expires)
    link = f"{config.web_base_url()}/reset?token={token}"
    return {"ok": True, "login": u["login"], "reset_link": link, "expires_min": 30}


@router.delete("/users/{user_id}")
async def admin_delete_user(user_id: int, admin_id: int = Depends(require_admin)):
    """Admins: delete user and all their data."""
    if user_id == admin_id:
        return JSONResponse({"error": "cannot_delete_self"}, status_code=400)
    admins = tenant.list_admins()
    if any(a["id"] == user_id for a in admins) and len(admins) <= 1:
        return JSONResponse({"error": "last_admin"}, status_code=400)
    u = tenant.get_user(user_id)
    if not u:
        return JSONResponse({"error": "user_not_found"}, status_code=404)
    tenant.delete_user(user_id)
    return {"ok": True}


@router.get("/user-apps")
async def admin_user_apps(user_id: int, admin_id: int = Depends(require_admin)):
    """Admins: per-user app access state for the toggles."""
    del admin_id
    return {"user_id": user_id, "apps": app_access.list_for_admin(user_id)}


@router.post("/user-apps")
async def admin_set_user_app(payload: dict, admin_id: int = Depends(require_admin)):
    """Admins: enable/disable a specific app for a user."""
    del admin_id
    user_id = payload.get("user_id")
    app_id = (payload.get("app_id") or "").strip()
    enabled = bool(payload.get("enabled"))
    if not isinstance(user_id, int) or not app_id:
        return JSONResponse({"error": "user_id and app_id required"}, status_code=400)
    try:
        app_access.set_access(user_id, app_id, enabled)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


@router.get("/logs")
async def admin_logs(lines: int = 200, admin_id: int = Depends(require_admin)):
    """Admins: tail of application log file."""
    del admin_id
    log_path = (db.DB_PATH.parent if db.DB_PATH else Path.home() / ".counta") / "counta.log"
    if not log_path.exists():
        return {"lines": [], "path": str(log_path)}
    lines = max(1, min(int(lines), 2000))
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        tail = f.readlines()[-lines:]
    return {"lines": tail, "path": str(log_path)}


@router.post("/restart")
async def admin_restart(admin_id: int = Depends(require_admin)):
    """Admins: ask the process to exit; launchd will restart it."""
    del admin_id
    async def _do_restart():
        await asyncio.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)
    asyncio.create_task(_do_restart())
    return {"ok": True, "message": "restarting"}
