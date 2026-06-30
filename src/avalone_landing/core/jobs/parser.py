"""Parsers for external Korean job boards."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import JobPost

_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


class BaseJobParser(ABC):
    """Abstract base for a job-board parser."""

    @property
    @abstractmethod
    def source_site(self) -> str:
        """Human-readable source identifier (used for filtering)."""

    @abstractmethod
    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        """Download and parse recent job postings."""


class KoreabridgeRSSParser(BaseJobParser):
    """Fetch and parse https://koreabridge.net/jobs.xml."""

    URL = "https://koreabridge.net/jobs.xml"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "koreabridge.net"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text, max_age_days)

    def parse(self, xml_text: str, max_age_days: int = 14) -> list[JobPost]:
        root = ET.fromstring(xml_text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        posts: list[JobPost] = []
        for item in root.findall(".//item"):
            title = self._text(item, "title")
            link = self._text(item, "link")
            guid = self._text(item, "guid")
            description = html.unescape(self._text(item, "description"))
            posted_at = self._parse_pubdate(self._text(item, "pubDate"))

            if posted_at is not None and posted_at < cutoff:
                continue

            author = self._text(item, "dc:creator", ns=_NS)
            posts.append(
                JobPost(
                    external_guid=guid or link,
                    source_site=self.source_site,
                    source_url=link,
                    title=title,
                    description_html=description,
                    description_text=self._html_to_text(description),
                    posted_at=posted_at,
                    author=author,
                    raw={
                        "title": title,
                        "description": description,
                        "pubDate": self._text(item, "pubDate"),
                        "creator": author,
                    },
                )
            )
        return posts

    def _text(self, item: ET.Element, tag: str, ns: dict[str, str] | None = None) -> str:
        element = item.find(tag, ns) if ns else item.find(tag)
        return (element.text or "").strip() if element is not None else ""

    def _parse_pubdate(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc)
        except ValueError:
            return None

    def _html_to_text(self, html_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class ExpatComKoreaParser(BaseJobParser):
    """Fetch and parse https://www.expat.com/en/jobs/asia/south-korea/."""

    URL = "https://www.expat.com/en/jobs/asia/south-korea/"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "expat.com"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text, max_age_days)

    def parse(self, html_text: str, max_age_days: int = 14) -> list[JobPost]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        offers_json = self._extract_offers_json(html_text)
        if not offers_json:
            return []

        posts: list[JobPost] = []
        for item in offers_json:
            posted_at = self._parse_date(item.get("date", ""))
            if posted_at is not None and posted_at < cutoff:
                continue

            title = (item.get("title") or "").strip()
            description = item.get("description") or ""
            description_text = self._html_to_text(description)
            link = (item.get("link") or "").strip()
            posts.append(
                JobPost(
                    external_guid=link or f"expat:{title}",
                    source_site=self.source_site,
                    source_url=link,
                    title=title,
                    description_html=description,
                    description_text=description_text,
                    posted_at=posted_at,
                    author=(item.get("name") or "").strip(),
                    raw=item,
                    employer=(item.get("name") or "").strip(),
                    location=(item.get("address") or "").strip(),
                    job_type=(item.get("contractType") or "").strip(),
                )
            )
        return posts

    def _extract_offers_json(self, html_text: str) -> list[dict[str, Any]]:
        match = re.search(
            r"var offers\s*=\s*(\{.*?\});",
            html_text,
            re.DOTALL,
        )
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
            return data.get("list", [])
        except json.JSONDecodeError:
            return []

    def _parse_date(self, value: str) -> datetime | None:
        # Format: "Added on 05/06/2026"
        value = value.strip()
        if not value:
            return None
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", value)
        if not m:
            return None
        try:
            return datetime(
                int(m.group(3)), int(m.group(2)), int(m.group(1)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None

    def _html_to_text(self, html_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class MultiSourceParser(BaseJobParser):
    """Aggregate posts from all configured sources."""

    def __init__(self, parsers: list[BaseJobParser] | None = None) -> None:
        self.parsers = parsers or [KoreabridgeRSSParser(), ExpatComKoreaParser()]

    @property
    def source_site(self) -> str:
        return "multi"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        posts: list[JobPost] = []
        for parser in self.parsers:
            try:
                posts.extend(parser.fetch(max_age_days))
            except Exception:  # noqa: BLE001
                # One source failing should not block the others.
                continue
        return posts
