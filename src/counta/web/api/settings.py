"""Counta API domain router."""

import logging

from fastapi import APIRouter

from counta.core import notify

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings():
    s = notify.get_settings()
    from counta.core.config import settings as cfg
    s["email_channel_ready"] = bool(cfg().smtp_user and cfg().smtp_password)
    return s


@router.post("/settings")
async def set_settings(payload: dict):
    return notify.set_settings(payload)
