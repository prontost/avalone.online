"""Password recovery flow: recover form, reset email, reset token consumption."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    import counta.core.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    import importlib
    import counta.core.tenant as tenant
    import counta.core.sqlledger as sl
    import counta.core.engine as engine
    import counta.core.global_settings as gs
    importlib.reload(tenant)
    importlib.reload(sl)
    importlib.reload(engine)
    importlib.reload(gs)
    tenant.set_current(1)

    from fastapi.testclient import TestClient
    from counta.web.app import app

    return TestClient(app)


def test_recover_password_sends_reset_link(client, monkeypatch):
    from counta.core import tenant, notify, security
    tid = tenant.create_user("alice", "secret", "alice@example.com")
    tenant.ensure_owner("owner", "ownerpass")

    sent = {}

    def fake_send_email(to, title, body):
        sent["to"] = to
        sent["title"] = title
        sent["body"] = body
        return True

    monkeypatch.setattr(notify, "_send_email", fake_send_email)
    # tolerate rate-limit helper by giving it a fresh ip each time if needed
    monkeypatch.setattr(security, "allow_recover", lambda ip: True)

    r = client.post("/recover", data={"mode": "pw", "query": "alice"}, follow_redirects=False)
    assert r.status_code == 200

    assert sent["to"] == "alice@example.com"
    assert "alice" in sent["body"]
    # extract token from the reset link
    import re
    m = re.search(r"/reset\?token=([a-zA-Z0-9_-]+)", sent["body"])
    assert m, "reset link with token not found in email body"
    token = m.group(1)
    # token must be consumable
    assert tenant.consume_reset_token(token) == tid


def test_reset_page_with_bad_token(client):
    r = client.post("/reset", data={"token": "bad", "password": "newsecret", "password2": "newsecret"})
    assert r.status_code == 200
    assert "Ссылка недействительна" in r.text or "invalid" in r.text.lower()


def test_reset_page_consumes_token_and_sets_password(client, monkeypatch):
    from counta.core import tenant, security
    tid = tenant.create_user("bob", "oldsecret", "bob@example.com")
    token = security.new_token()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
    tenant.set_reset_token(tid, token, expires)

    r = client.post("/reset", data={"token": token, "password": "newsecret", "password2": "newsecret"})
    assert r.status_code == 200
    assert tenant.authenticate("bob", "newsecret") == tid
    assert tenant.authenticate("bob", "oldsecret") is None
    # token consumed
    assert tenant.consume_reset_token(token) is None


def test_reset_page_enforces_strict_policy(client, monkeypatch):
    from counta.core import config, tenant, security
    monkeypatch.setattr(config, "strict_password_policy", lambda: True)
    tid = tenant.create_user("carol", "oldsecret", "carol@example.com")
    token = security.new_token()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
    tenant.set_reset_token(tid, token, expires)

    # weak password should be rejected
    r = client.post("/reset", data={"token": token, "password": "weak", "password2": "weak"})
    assert r.status_code == 200
    assert tenant.authenticate("carol", "weak") is None

    # strong password should be accepted
    r = client.post("/reset", data={"token": token, "password": "Str0ng!Pass", "password2": "Str0ng!Pass"})
    assert r.status_code == 200
    assert tenant.authenticate("carol", "Str0ng!Pass") == tid
