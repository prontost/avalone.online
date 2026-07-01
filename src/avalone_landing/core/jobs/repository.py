"""Persistence layer for aggregated job postings."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from avalone_core.db import connection

from .models import JobPost


class JobPostRepository:
    """Store and retrieve ``JobPost`` rows from the unified Avalone database."""

    def save(self, post: JobPost) -> tuple[int, str]:
        """Insert a post or update it only if content changed.

        Returns (row_id, status) where status is one of:
        'inserted', 'updated', 'unchanged'.
        """
        with connection() as con:
            existing = con.execute(
                "SELECT id, content_hash, title_translated, description_translated FROM work_job_posts WHERE external_guid = ?",
                (post.external_guid,),
            ).fetchone()

            if existing is None:
                row = self._post_to_row(post)
                cur = con.execute(
                    "INSERT INTO work_job_posts (external_guid, source_site, source_url, title, title_translated, description_html, description_text, description_translated, employer, contact_phone, contact_email, visa_type, location, job_type, salary, pay_type, content_hash, country, posted_at, parsed_at, raw_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
                self._save_legacy_translation(con, post)
                con.commit()
                return cur.lastrowid or 0, "inserted"

            if existing["content_hash"] == post.content_hash:
                # Content unchanged: only refresh parsed_at and raw_json for observability.
                con.execute(
                    "UPDATE work_job_posts SET parsed_at = ?, raw_json = ? WHERE id = ?",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(post.raw, ensure_ascii=False) if post.raw else None,
                        existing["id"],
                    ),
                )
                con.commit()
                return existing["id"], "unchanged"

            # Content changed: update all fields except posted_at and existing translations.
            title_translated = existing["title_translated"] or ""
            description_translated = existing["description_translated"] or ""
            con.execute(
                """
                UPDATE work_job_posts SET
                    source_site = ?,
                    source_url = ?,
                    title = ?,
                    title_translated = ?,
                    description_html = ?,
                    description_text = ?,
                    description_translated = ?,
                    employer = ?,
                    contact_phone = ?,
                    contact_email = ?,
                    visa_type = ?,
                    location = ?,
                    job_type = ?,
                    salary = ?,
                    pay_type = ?,
                    content_hash = ?,
                    country = ?,
                    parsed_at = ?,
                    raw_json = ?
                WHERE id = ?
                """,
                (
                    post.source_site,
                    post.source_url,
                    post.title,
                    title_translated,
                    post.description_html,
                    post.description_text,
                    description_translated,
                    post.employer,
                    post.contact_phone,
                    post.contact_email,
                    post.visa_type,
                    post.location,
                    post.job_type,
                    post.salary,
                    post.pay_type,
                    post.content_hash,
                    post.country,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(post.raw, ensure_ascii=False) if post.raw else None,
                    existing["id"],
                ),
            )
            self._save_legacy_translation(con, post)
            con.commit()
            return existing["id"], "updated"

    def list_recent(
        self,
        limit: int = 100,
        offset: int = 0,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
        country: str | None = None,
        query_lang: str = "ru",
        exclude_guids: list[str] | None = None,
        include_only_guids: list[str] | None = None,
    ) -> list[JobPost]:
        """Return recent posts with optional filters."""
        where, params = self._build_where(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
            country=country,
            query_lang=query_lang,
            exclude_guids=exclude_guids,
            include_only_guids=include_only_guids,
        )

        sql = (
            "SELECT * FROM work_job_posts "
            + ("WHERE " + " AND ".join(where) if where else "")
            + " ORDER BY COALESCE(posted_at, parsed_at) DESC "
            + "LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        with connection() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._row_to_post(r) for r in rows]

    def count_recent(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
        country: str | None = None,
        query_lang: str = "ru",
        exclude_guids: list[str] | None = None,
        include_only_guids: list[str] | None = None,
    ) -> int:
        where, params = self._build_where(
            location=location,
            source_site=source_site,
            max_age_days=max_age_days,
            query=query,
            visa_type=visa_type,
            job_type=job_type,
            country=country,
            query_lang=query_lang,
            exclude_guids=exclude_guids,
            include_only_guids=include_only_guids,
        )
        sql = (
            "SELECT COUNT(*) AS n FROM work_job_posts "
            + ("WHERE " + " AND ".join(where) if where else "")
        )
        with connection() as con:
            row = con.execute(sql, params).fetchone()
        return row["n"] if row else 0

    def _build_where(
        self,
        location: str | None = None,
        source_site: str | None = None,
        max_age_days: int | None = None,
        query: str | None = None,
        visa_type: str | None = None,
        job_type: str | None = None,
        country: str | None = None,
        query_lang: str = "ru",
        exclude_guids: list[str] | None = None,
        include_only_guids: list[str] | None = None,
    ) -> tuple[list[str], list[Any]]:
        where: list[str] = []
        params: list[Any] = []
        if source_site:
            where.append("source_site = ?")
            params.append(source_site)
        if location:
            where.append("(location LIKE ? OR title LIKE ? OR description_text LIKE ?)")
            like = f"%{location}%"
            params.extend([like, like, like])
        if max_age_days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
            where.append("COALESCE(posted_at, parsed_at) >= ?")
            params.append(cutoff)
        if query:
            q = f"%{query}%"
            where.append(
                "(title LIKE ? OR description_text LIKE ? OR employer LIKE ? OR location LIKE ? "
                "OR EXISTS (SELECT 1 FROM work_post_translations t "
                "WHERE t.external_guid = work_job_posts.external_guid AND t.lang = ? "
                "AND (t.title LIKE ? OR t.description LIKE ?)))"
            )
            params.extend([q, q, q, q, query_lang, q, q])
        if visa_type:
            where.append("visa_type LIKE ?")
            params.append(f"%{visa_type}%")
        if job_type:
            where.append("(job_type LIKE ? OR title LIKE ? OR description_text LIKE ?)")
            j = f"%{job_type}%"
            params.extend([j, j, j])
        if country:
            where.append("country = ?")
            params.append(country)
        if exclude_guids:
            placeholders = ",".join("?" * len(exclude_guids))
            where.append(f"external_guid NOT IN ({placeholders})")
            params.extend(exclude_guids)
        if include_only_guids:
            placeholders = ",".join("?" * len(include_only_guids))
            where.append(f"external_guid IN ({placeholders})")
            params.extend(include_only_guids)
        return where, params

    def list_untranslated(
        self,
        limit: int = 100,
        max_age_days: int | None = None,
        lang: str = "ru",
    ) -> list[JobPost]:
        """Return posts that have no translation for ``lang`` yet, oldest first.

        Args:
            limit: Maximum rows to return.
            max_age_days: If set, ignore posts older than this many days.
            lang: Target language code.
        """
        where = [
            "NOT EXISTS (SELECT 1 FROM work_post_translations t "
            "WHERE t.external_guid = work_job_posts.external_guid AND t.lang = ?)"
        ]
        params: list[Any] = [lang]
        if max_age_days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
            where.append("COALESCE(posted_at, parsed_at) >= ?")
            params.append(cutoff)
        sql = (
            "SELECT * FROM work_job_posts "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY COALESCE(posted_at, parsed_at) ASC "
            "LIMIT ?"
        )
        params.append(limit)
        with connection() as con:
            rows = con.execute(sql, params).fetchall()
        return [self._row_to_post(r) for r in rows]

    def list_since(
        self,
        since: datetime,
        limit: int = 50,
    ) -> list[JobPost]:
        """Return posts published or parsed since ``since`` (UTC), newest first."""
        iso = since.isoformat()
        sql = (
            "SELECT * FROM work_job_posts "
            "WHERE COALESCE(posted_at, parsed_at) >= ? "
            "ORDER BY COALESCE(posted_at, parsed_at) DESC "
            "LIMIT ?"
        )
        with connection() as con:
            rows = con.execute(sql, (iso, limit)).fetchall()
        return [self._row_to_post(r) for r in rows]

    def update_translations(
        self,
        external_guid: str,
        title_translated: str,
        description_translated: str,
        lang: str = "ru",
    ) -> None:
        with connection() as con:
            con.execute(
                """
                INSERT INTO work_post_translations (external_guid, lang, title, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(external_guid, lang) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    updated_at = excluded.updated_at
                """,
                (
                    external_guid,
                    lang,
                    title_translated,
                    description_translated,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            con.commit()

    def _save_legacy_translation(self, con: sqlite3.Connection, post: JobPost) -> None:
        """Persist legacy title_translated/description_translated into the new table."""
        title = (post.title_translated or "").strip()
        description = (post.description_translated or "").strip()
        if not title and not description:
            return
        con.execute(
            """
            INSERT INTO work_post_translations (external_guid, lang, title, description, updated_at)
            VALUES (?, 'ru', ?, ?, ?)
            ON CONFLICT(external_guid, lang) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                updated_at = excluded.updated_at
            """,
            (
                post.external_guid,
                title or None,
                description or None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def get_translation(self, external_guid: str, lang: str) -> dict[str, str]:
        with connection() as con:
            row = con.execute(
                "SELECT title, description FROM work_post_translations "
                "WHERE external_guid = ? AND lang = ?",
                (external_guid, lang),
            ).fetchone()
        if row:
            return {"title": row["title"] or "", "description": row["description"] or ""}
        return {"title": "", "description": ""}

    def get_translations(
        self, external_guids: list[str], lang: str
    ) -> dict[str, dict[str, str]]:
        if not external_guids:
            return {}
        placeholders = ",".join("?" * len(external_guids))
        with connection() as con:
            rows = con.execute(
                f"SELECT external_guid, title, description FROM work_post_translations "
                f"WHERE lang = ? AND external_guid IN ({placeholders})",
                (lang, *external_guids),
            ).fetchall()
        return {
            row["external_guid"]: {"title": row["title"] or "", "description": row["description"] or ""}
            for row in rows
        }

    def list_sources(self) -> list[str]:
        """Return all distinct source_site values currently in the DB."""
        sql = "SELECT DISTINCT source_site FROM work_job_posts ORDER BY source_site"
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["source_site"] for r in rows if r["source_site"]]

    def list_locations(self) -> list[str]:
        """Return distinct non-empty location values."""
        sql = (
            "SELECT DISTINCT location FROM work_job_posts "
            "WHERE location IS NOT NULL AND location != '' ORDER BY location"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["location"] for r in rows]

    def list_countries(self) -> list[str]:
        sql = (
            "SELECT DISTINCT country FROM work_job_posts "
            "WHERE country IS NOT NULL AND country != '' ORDER BY country"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["country"] for r in rows]

    def list_pay_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT pay_type FROM work_job_posts "
            "WHERE pay_type IS NOT NULL AND pay_type != '' ORDER BY pay_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["pay_type"] for r in rows]

    def list_visa_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT visa_type FROM work_job_posts "
            "WHERE visa_type IS NOT NULL AND visa_type != '' ORDER BY visa_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return sorted({v.strip() for row in rows for v in row["visa_type"].split(",") if v.strip()})

    def list_job_types(self) -> list[str]:
        sql = (
            "SELECT DISTINCT job_type FROM work_job_posts "
            "WHERE job_type IS NOT NULL AND job_type != '' ORDER BY job_type"
        )
        with connection() as con:
            rows = con.execute(sql).fetchall()
        return [r["job_type"] for r in rows]

    def count(self) -> int:
        with connection() as con:
            row = con.execute("SELECT COUNT(*) AS n FROM work_job_posts").fetchone()
        return row["n"] if row else 0

    def _post_to_row(self, post: JobPost) -> tuple[Any, ...]:
        return (
            post.external_guid,
            post.source_site,
            post.source_url,
            post.title,
            post.title_translated,
            post.description_html,
            post.description_text,
            post.description_translated,
            post.employer,
            post.contact_phone,
            post.contact_email,
            post.visa_type,
            post.location,
            post.job_type,
            post.salary,
            post.pay_type,
            post.content_hash,
            post.country,
            post.posted_at.isoformat() if post.posted_at else None,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(post.raw, ensure_ascii=False) if post.raw else None,
        )

    def _row_to_post(self, row: sqlite3.Row) -> JobPost:
        posted_at = None
        if row["posted_at"]:
            try:
                posted_at = datetime.fromisoformat(row["posted_at"])
            except ValueError:
                posted_at = None
        raw = {}
        if row["raw_json"]:
            try:
                raw = json.loads(row["raw_json"])
            except json.JSONDecodeError:
                raw = {}
        return JobPost(
            external_guid=row["external_guid"],
            source_site=row["source_site"],
            source_url=row["source_url"],
            title=row["title"],
            description_html=row["description_html"] or "",
            description_text=row["description_text"] or "",
            posted_at=posted_at,
            author=raw.get("creator", ""),
            raw=raw,
            title_translated=row["title_translated"] or "",
            description_translated=row["description_translated"] or "",
            employer=row["employer"] or "",
            contact_phone=row["contact_phone"] or "",
            contact_email=row["contact_email"] or "",
            visa_type=row["visa_type"] or "",
            location=row["location"] or "",
            job_type=row["job_type"] or "",
            salary=row["salary"] or "",
            pay_type=row["pay_type"] or "",
            content_hash=row["content_hash"] or "",
            country=row["country"] or "",
        )
