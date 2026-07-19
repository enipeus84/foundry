"""Authentication tests for the web layer. Skip cleanly without the
[web] extra, like the rest of the web suite."""

import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.web import app  # noqa: E402

ALLOWED = "cparkerbrads@gmail.com"


@pytest.fixture(autouse=True)
def auth_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    # An isolated event log per test: rendering "/" must never touch a
    # real data path from the test suite.
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))


def client() -> TestClient:
    return TestClient(app, follow_redirects=False)


def _session_cookie(email: str) -> str:
    return webauth.session_token(email, webauth.load_config())


def test_unauthenticated_root_redirects_to_login():
    r = client().get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_health_remains_public():
    r = client().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_page_shows_google_button():
    r = client().get("/login")
    assert r.status_code == 200
    assert "Continue with Google" in r.text
    assert '/auth/google' in r.text


def test_auth_google_redirects_to_supabase_with_pkce():
    r = client().get("/auth/google")
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("https://example.supabase.co/auth/v1/authorize")
    assert "provider=google" in loc
    assert "code_challenge=" in loc and "code_challenge_method=s256" in loc
    assert webauth.VERIFIER_COOKIE in r.cookies


def test_allowed_user_can_access_root():
    c = client()
    c.cookies.set(webauth.SESSION_COOKIE, _session_cookie(ALLOWED))
    r = c.get("/")
    assert r.status_code == 200
    assert "MISSION CONTROL" in r.text


def test_non_allowed_user_is_rejected_at_callback(monkeypatch):
    monkeypatch.setattr(webauth, "exchange_code",
                        lambda cfg, code, verifier: "intruder@gmail.com")
    c = client()
    # Prime the PKCE verifier cookie as /auth/google would.
    cfg = webauth.load_config()
    c.cookies.set(webauth.VERIFIER_COOKIE, webauth.sign(
        {"v": "verifier", "exp": int(time.time()) + 60}, cfg.session_secret))
    r = c.get("/auth/callback?code=fake")
    assert r.status_code == 403
    assert "not authorised" in r.text
    assert webauth.SESSION_COOKIE not in r.cookies


def test_allowed_user_callback_sets_session_and_redirects(monkeypatch):
    monkeypatch.setattr(webauth, "exchange_code",
                        lambda cfg, code, verifier: ALLOWED)
    c = client()
    cfg = webauth.load_config()
    c.cookies.set(webauth.VERIFIER_COOKIE, webauth.sign(
        {"v": "verifier", "exp": int(time.time()) + 60}, cfg.session_secret))
    r = c.get("/auth/callback?code=fake")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    token = r.cookies.get(webauth.SESSION_COOKIE)
    assert token and webauth.session_email(token, cfg) == ALLOWED
    # Cookie hardening
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie


def test_forged_session_is_rejected():
    c = client()
    c.cookies.set(webauth.SESSION_COOKIE,
                  webauth.session_token(ALLOWED, webauth.load_config())[:-3]
                  + "xxx")
    r = c.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_stale_session_rejected_when_email_no_longer_allowed(monkeypatch):
    """An old session for a previously-allowed address must not survive
    a change of FOUNDRY_ALLOWED_EMAIL."""
    token = _session_cookie("old@gmail.com")
    c = client()
    c.cookies.set(webauth.SESSION_COOKIE, token)
    r = c.get("/")
    assert r.status_code == 303


def test_logout_clears_session():
    c = client()
    c.cookies.set(webauth.SESSION_COOKIE, _session_cookie(ALLOWED))
    r = c.get("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    sc = r.headers["set-cookie"]
    assert webauth.SESSION_COOKIE in sc and ("Max-Age=0" in sc or "max-age=0" in sc)
    # And the session is genuinely gone for a fresh request using the
    # cleared cookie jar.
    c.cookies.delete(webauth.SESSION_COOKIE)
    assert c.get("/").status_code == 303


def test_fail_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("FOUNDRY_ALLOWED_EMAIL")
    c = client()
    c.cookies.set(webauth.SESSION_COOKIE, _session_cookie(""))
    r = c.get("/")
    assert r.status_code == 303  # nobody gets in when config is absent
