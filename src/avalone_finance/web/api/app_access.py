"""API для реестра приложений и доступа текущего пользователя."""

from fastapi import APIRouter, Depends, HTTPException, status

from avalone_finance.core.app_access_service import AppAccessService
from avalone_finance.web.api.dependencies import current_tenant, get_app_access_service

router = APIRouter(prefix="/apps")


@router.get("")
async def apps_registry(
    service: AppAccessService = Depends(get_app_access_service),
):
    """Публичный реестр всех приложений платформы."""
    return {"apps": service.registry()}


@router.get("/my")
async def my_apps(
    tenant_id: int = Depends(current_tenant),
    service: AppAccessService = Depends(get_app_access_service),
):
    """Список приложений, доступных текущему пользователю."""
    return {"apps": service.list_for_user(tenant_id)}
