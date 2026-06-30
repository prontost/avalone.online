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
from bs4 import BeautifulSoup

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
                    country="KR",
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


class AlbamonParser(BaseJobParser):
    """Fetch and parse the Albamon mobile homepage.

    Albamon is a major Korean part-time / arbeit job board. The mobile
    homepage embeds the job list inside ``window.__NEXT_DATA__``.
    """

    URL = "https://m.albamon.com/"
    USER_AGENT = (
        "Mozilla/5.0 (Linux; Android 10; SM-G973F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "albamon.com"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        # max_age_days is accepted for interface compatibility; Albamon
        # homepage always returns currently featured postings.
        del max_age_days
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.URL)
        response.raise_for_status()
        return self.parse(response.text)

    def parse(self, html_text: str) -> list[JobPost]:
        data = self._extract_next_data(html_text)
        if not data:
            return []

        seen: set[int] = set()
        posts: list[JobPost] = []
        for item in self._walk_collections(data):
            recruit_no = item.get("recruitNo")
            if not recruit_no or recruit_no in seen:
                continue
            seen.add(recruit_no)

            title = (item.get("recruitTitle") or "").strip()
            area = (item.get("workplaceArea") or "").strip()
            company = (item.get("companyName") or "").strip()
            pay = (item.get("pay") or "").strip()
            pay_type = ""
            pay_type_key = ""
            if isinstance(item.get("payType"), dict):
                pay_type = (item["payType"].get("description") or "").strip()
                pay_type_key = (item["payType"].get("key") or "").strip()

            posts.append(
                JobPost(
                    external_guid=f"albamon:{recruit_no}",
                    source_site=self.source_site,
                    source_url=f"https://m.albamon.com/jobs/detail/{recruit_no}",
                    title=title,
                    description_html="",
                    description_text=self._build_description(item),
                    author=company,
                    raw=item,
                    employer=company,
                    location=area,
                    salary=pay,
                    pay_type=pay_type,
                    job_type=self._pay_type_to_job_type(pay_type_key),
                    country="KR",
                )
            )
        return posts

    def _extract_next_data(self, html_text: str) -> dict[str, Any] | None:
        match = re.search(
            r'id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html_text,
            re.DOTALL,
        )
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _walk_collections(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        queries = (
            data.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [])
        )
        for query in queries:
            state = query.get("state", {})
            payload = state.get("data", {})
            if isinstance(payload, dict) and isinstance(payload.get("collection"), list):
                items.extend(payload["collection"])
            elif isinstance(payload, list):
                items.extend(payload)
        return items

    def _build_description(self, item: dict[str, Any]) -> str:
        parts = [
            (item.get("payType") or {}).get("description", ""),
            item.get("pay", ""),
            item.get("workplaceArea", ""),
            item.get("companyName", ""),
        ]
        return "\n".join(p for p in parts if p).strip()

    @staticmethod
    def _pay_type_to_job_type(pay_type_key: str) -> str:
        mapping = {
            "HOURLY_WAGE": "Part-time / hourly",
            "DAILY_WAGE": "Daily pay",
            "MONTHLY_SALARY": "Full-time / monthly",
            "YEARLY_SALARY": "Full-time / yearly",
            "PER_TASK": "Per task",
        }
        return mapping.get(pay_type_key, "")


class SaraminParser(BaseJobParser):
    """Fetch and parse Saramin search results (full-time / contract jobs)."""

    SEARCH_URL = "https://www.saramin.co.kr/zf_user/search/recruit"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    @property
    def source_site(self) -> str:
        return "saramin.co.kr"

    def fetch(self, max_age_days: int = 14) -> list[JobPost]:
        # Saramin search is SSR HTML; we parse the first results page.
        params = {"searchword": "외국인"}
        with httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(self.SEARCH_URL, params=params)
        response.raise_for_status()
        return self.parse(response.text)

    def parse(self, html_text: str) -> list[JobPost]:
        soup = BeautifulSoup(html_text, "html.parser")
        posts: list[JobPost] = []
        for item in soup.select(".item_recruit"):
            title_a = item.select_one(".job_tit a")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)
            href = title_a.get("href", "")
            rec_idx = self._extract_rec_idx(href)
            if not rec_idx:
                continue

            company_a = item.select_one(".corp_name a")
            company = company_a.get_text(strip=True) if company_a else ""
            condition_el = item.select_one(".job_condition")
            condition = condition_el.get_text(" ", strip=True) if condition_el else ""
            date_el = item.select_one(".job_date .date")
            date_text = date_el.get_text(strip=True) if date_el else ""

            job_type = self._extract_job_type(condition)
            posted_at = self._parse_date(date_text)

            posts.append(
                JobPost(
                    external_guid=f"saramin:{rec_idx}",
                    source_site=self.source_site,
                    source_url=f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rec_idx}",
                    title=title,
                    description_html=str(item),
                    description_text=f"{condition}\n{date_text}".strip(),
                    posted_at=posted_at,
                    author=company,
                    employer=company,
                    location=self._extract_location(condition),
                    job_type=job_type,
                    country="KR",
                    raw={
                        "title": title,
                        "company": company,
                        "condition": condition,
                        "date_text": date_text,
                        "rec_idx": rec_idx,
                    },
                )
            )
        return posts

    def _extract_rec_idx(self, href: str) -> str:
        match = re.search(r"[?&]rec_idx=(\d+)", href)
        return match.group(1) if match else ""

    def _extract_location(self, condition: str) -> str:
        # Conditions look like: "서울 강남구 경력무관 학력무관 정규직"
        parts = condition.split()
        if parts and parts[0] in ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종"):
            return " ".join(parts[:2]) if len(parts) > 1 else parts[0]
        if parts and parts[0] in ("경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"):
            return " ".join(parts[:2]) if len(parts) > 1 else parts[0]
        return ""

    def _extract_job_type(self, condition: str) -> str:
        if "정규직" in condition:
            return "Full-time"
        if "계약직" in condition:
            return "Contract"
        if "기간제" in condition:
            return "Fixed-term"
        if "인턴" in condition:
            return "Internship"
        return ""

    def _parse_date(self, value: str) -> datetime | None:
        if not value:
            return None
        value = value.strip()
        now = datetime.now(timezone.utc)
        # "~ 08/11(화)" is an application deadline, not a posting date.
        if value.startswith("~"):
            return None
        if "오늘마감" in value or value == "오늘":
            return now
        if "내일마감" in value or value == "내일":
            return now + timedelta(days=1)
        return None


class MultiSourceParser(BaseJobParser):
    """Aggregate posts from all configured sources."""

    def __init__(self, parsers: list[BaseJobParser] | None = None) -> None:
        self.parsers = parsers or [KoreabridgeRSSParser(), AlbamonParser(), SaraminParser()]

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
