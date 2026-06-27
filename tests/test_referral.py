"""Tests for the referral code system."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from avalone_core.referral_service import ReferralService
from avalone_landing.core.auth_service import AuthService
from avalone_landing.web.app import app


def _session_token_from(response) -> str:
    set_cookie = response.headers.get("set-cookie") or ""
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("avalone_session="):
            return part.split("=", 1)[1]
    raise RuntimeError("no avalone_session cookie in response")


def _auth_client(login: str, password: str = "password", invite: str = "") -> TestClient:
    AuthService.cookie_domain = lambda self, request: None
    client = TestClient(app)
    resp = client.post(
        "/register",
        data={"login": login, "password": password, "password2": password, "invite": invite},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    token = _session_token_from(resp)
    client.headers["Cookie"] = f"avalone_session={token}"
    return client


def test_referral_code_created_lazily():
    client = _auth_client("referrer")
    resp = client.get("/api/referral/code")
    assert resp.status_code == 200
    data = resp.json()
    code = data["code"]
    assert len(code) == 8
    assert code == code.upper()
    assert data["url"] == f"https://avalone.online?ref={code}"

    # Second call returns the same code.
    assert client.get("/api/referral/code").json()["code"] == code


def test_referral_stats():
    client = _auth_client("stats_user")
    stats = client.get("/api/referral/stats").json()
    assert stats["invitees_count"] == 0
    assert stats["invitees"] == []
    assert stats["url"].endswith("?ref=" + stats["code"])


def test_registration_with_referral_code():
    referrer = _auth_client("the_referrer")
    code = referrer.get("/api/referral/code").json()["code"]

    invitee = _auth_client("the_invitee", invite=code)
    # The new user must not see themselves as invitees on their own stats.
    assert invitee.get("/api/referral/stats").json()["invitees_count"] == 0

    stats = referrer.get("/api/referral/stats")
    assert stats.status_code == 200
    data = stats.json()
    assert data["invitees_count"] == 1
    assert data["invitees"][0]["login"] == "the_invitee"


def test_no_self_referral():
    client = _auth_client("self_ref")
    code = client.get("/api/referral/code").json()["code"]
    user_id = client.get("/auth/me").json()["id"]
    assert ReferralService().apply_referral(user_id, code, None) is False


def test_referral_endpoints_require_auth():
    client = TestClient(app)
    assert client.get("/api/referral/code").status_code == 401
    assert client.get("/api/referral/stats").status_code == 401
