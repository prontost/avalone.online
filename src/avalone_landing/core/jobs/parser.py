"""RSS parser for the Koreabridge job board."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import JobPost

_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


class KoreabridgeRSSParser:
    """Fetch and parse https://koreabridge.net/jobs.xml.

    Returns only posts published within the last ``max_age_days``.
    """

    URL = "https://koreabridge.net/jobs.xml"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    def __init__(self, max_age_days: int = 14) -> None:
        self.max_age_days = max_age_days

    def fetch(self) -> list[JobPost]:
        """Download the RSS feed and convert it to ``JobPost`` objects."""
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text)

    def parse(self, xml_text: str) -> list[JobPost]:
        """Parse RSS XML text into a list of recent ``JobPost`` objects."""
        root = ET.fromstring(xml_text)
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
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
                    source_site="koreabridge.net",
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
