"""Web routes for the Avalone Work branch."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from avalone_landing.core.jobs.service import JobPostService
from avalone_landing.web.dependencies import current_user, get_shell_context
from avalone_landing.web.shell_context import ShellContext

router = APIRouter(prefix="/work")


def _shell_context(request: Request, shell_context: ShellContext):
    """Build the shell context for work pages."""
    from avalone_landing.web.app import BUILD_ID, templates

    return shell_context.build(
        templates,
        request,
        current_app="work",
        app_nav=[],
        build_id=BUILD_ID,
    )


@router.get("", response_class=HTMLResponse)
async def work_index(
    request: Request,
    location: str = "",
    source: str = "",
    days: str = "14",
    user=Depends(current_user),
    shell_context: ShellContext = Depends(get_shell_context),
):
    """Render the job-postings feed with filters."""
    from avalone_landing.web.app import _no_cache, templates

    ctx = _shell_context(request, shell_context)
    service = JobPostService()

    try:
        max_age_days = int(days) if days else None
    except ValueError:
        max_age_days = 14

    jobs = service.list_recent(
        limit=200,
        location=location or None,
        source_site=source or None,
        max_age_days=max_age_days,
    )

    ctx.update(
        {
            "jobs": jobs,
            "sources": service.repository.list_sources(),
            "locations": service.repository.list_locations(),
            "selected_location": location,
            "selected_source": source,
            "selected_days": str(max_age_days) if max_age_days is not None else "",
        }
    )
    return _no_cache(templates.TemplateResponse(request, "work.html", ctx))


@router.post("/fetch", response_class=RedirectResponse)
async def work_fetch(request: Request, days: str = "14"):
    """Trigger a fresh fetch from the configured job boards."""
    try:
        max_age_days = int(days) if days else 14
    except ValueError:
        max_age_days = 14
    JobPostService().fetch_and_store(max_age_days=max_age_days)
    return RedirectResponse(f"/work?days={max_age_days}", status_code=303)
