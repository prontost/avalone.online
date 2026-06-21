"""FastAPI dependencies shared by API routers."""

from fastapi import Depends, HTTPException, status

from counta.core import tenant


def current_tenant() -> int:
    """Return the tenant_id set by the auth middleware."""
    return tenant.require_current()


# alias for routes that need any authenticated user
require_user = current_tenant


def require_admin(tid: int = Depends(current_tenant)) -> int:
    """Ensure the current tenant is an instance admin."""
    if not tenant.is_admin(tid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )
    return tid
