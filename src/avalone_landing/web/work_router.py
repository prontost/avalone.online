"""Web routes for the Avalone Work branch."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from avalone_landing.core.jobs.location_repository import LocationTranslationRepository
from avalone_landing.core.jobs.service import JobPostService
from avalone_landing.web.dependencies import current_user, get_shell_context
from avalone_landing.web.shell_context import ShellContext

router = APIRouter(prefix="/work")

PAGE_SIZE = 20


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
    q: str = "",
    visa: str = "",
    job_type: str = "",
    country: str = "",
    loc_lang: str = "ru",
    page: str = "1",
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
    try:
        current_page = int(page) if page else 1
    except ValueError:
        current_page = 1
    if current_page < 1:
        current_page = 1
    offset = (current_page - 1) * PAGE_SIZE

    filters = {
        "location": location or None,
        "source_site": source or None,
        "max_age_days": max_age_days,
        "query": q or None,
        "visa_type": visa or None,
        "job_type": job_type or None,
        "country": country or None,
    }

    total = service.count_recent(**filters)
    jobs = service.list_recent(limit=PAGE_SIZE, offset=offset, **filters)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    loc_repo = LocationTranslationRepository()
    loc_repo.ensure_schema()

    def _display_location(raw: str) -> str:
        return loc_repo.get(raw, loc_lang) or raw

    ctx.update(
        {
            "jobs": jobs,
            "sources": service.repository.list_sources(),
            "locations": service.repository.list_locations(),
            "location_labels": {
                loc: _display_location(loc) for loc in service.repository.list_locations()
            },
            "pay_types": service.repository.list_pay_types(),
            "visa_types": service.repository.list_visa_types(),
            "job_types": service.repository.list_job_types(),
            "countries": service.repository.list_countries(),
            "selected_location": location,
            "selected_source": source,
            "selected_days": str(max_age_days) if max_age_days is not None else "",
            "selected_query": q,
            "selected_visa": visa,
            "selected_job_type": job_type,
            "selected_country": country,
            "selected_loc_lang": loc_lang,
            "current_page": current_page,
            "total_pages": total_pages,
            "total_jobs": total,
            "page_size": PAGE_SIZE,
        }
    )
    return _no_cache(templates.TemplateResponse(request, "work.html", ctx))


@router.get("/events")
async def work_events(request: Request):
    """Server-Sent Events stream for new job postings."""
    service = JobPostService()
    last_check = datetime.now(timezone.utc)

    async def event_generator():
        nonlocal last_check
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(5)
            try:
                new_posts = service.repository.list_since(last_check)
            except Exception:
                new_posts = []
            if new_posts:
                last_check = datetime.now(timezone.utc)
                payload = json.dumps(
                    {
                        "count": len(new_posts),
                        "latest_id": new_posts[0].external_guid,
                    },
                    ensure_ascii=False,
                )
                yield f"event: new-posts\ndata: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
