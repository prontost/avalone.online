"""Tests for device fingerprinting and screen-time tracking."""

from __future__ import annotations

from fastapi.testclient import TestClient

from avalone_core.device_service import DeviceService
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


def test_heartbeat_increments_screen_time():
    client = _auth_client("screen_user")

    payload = {"device_id": "device-1", "screen": "390x844", "platform": "iOS", "seconds": 5}
    resp = client.post("/api/heartbeat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["today_seconds"] == 5
    assert data["total_seconds"] == 5

    payload["seconds"] = 10
    resp = client.post("/api/heartbeat", json=payload)
    assert resp.status_code == 200
    assert resp.json()["today_seconds"] == 15
    assert resp.json()["total_seconds"] == 15


def test_heartbeat_caps_seconds():
    client = _auth_client("cap_user")

    payload = {"device_id": "device-2", "screen": "390x844", "platform": "Android", "seconds": 100}
    resp = client.post("/api/heartbeat", json=payload)
    assert resp.status_code == 200
    # Capped at 60 seconds per heartbeat.
    assert resp.json()["today_seconds"] == 60
    assert resp.json()["total_seconds"] == 60


def test_heartbeat_registers_device():
    client = _auth_client("device_user")
    user_id = client.get("/auth/me").json()["id"]

    payload = {"device_id": "device-3", "screen": "800x600", "platform": "macOS", "seconds": 5}
    resp = client.post(
        "/api/heartbeat", json=payload, headers={"user-agent": "TestAgent/1.0"}
    )
    assert resp.status_code == 200
    assert resp.json()["device_id"] == "device-3"

    devices = DeviceService()._repo.user_devices(user_id)
    assert len(devices) == 1
    assert devices[0]["device_id"] == "device-3"
    assert devices[0]["platform"] == "macOS"


def test_heartbeat_requires_auth():
    client = TestClient(app)
    resp = client.post(
        "/api/heartbeat",
        json={"device_id": "x", "screen": "100x100", "platform": "test"},
    )
    assert resp.status_code == 401
