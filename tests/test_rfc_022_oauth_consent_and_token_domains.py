"""RFC-022: OAuth authority requires explicit approval; tokens are domain-bound.

Two invariants are under test:

1. Navigation is not consent. A GET on a valid pending consent URL renders an
   approval surface, issues nothing, and leaves the pending request intact.
2. A signed token is only authority inside the domain it was issued for.
"""

from __future__ import annotations

import base64
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")

from foundry import webauth  # noqa: E402
from tests.test_rfc_021_mcp_remote_transport import _client  # noqa: E402


ATTACKER_REDIRECT = "https://attacker.invalid/collect"
ATTACKER_VERIFIER = "attacker-controlled-pkce-verifier"


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _register(client, redirect_uri: str, name: str) -> str:
    registered = client.post("/mcp/register", json={
        "client_name": name,
        "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    })
    assert registered.status_code == 201, registered.text
    return registered.json()["client_id"]


def _authorize(client, client_id: str, redirect_uri: str, verifier: str) -> str:
    """Return the consent URL a client is sent to."""
    response = client.get("/mcp/authorize", params={
        "client_id": client_id, "response_type": "code",
        "code_challenge": _challenge(verifier), "code_challenge_method": "S256",
        "redirect_uri": redirect_uri,
    }, follow_redirects=False)
    assert response.status_code == 302
    return response.headers["location"]


def _sign_in(client) -> None:
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
        "remote@example.com", webauth.load_config()))


def _approval_fields(body: str) -> dict[str, str]:
    return dict(re.findall(r'name="(\w+)" value="([^"]+)"', body))


def _completion_target(response) -> str:
    """The client URL offered as a link by a successful approval."""
    assert response.status_code == 200
    assert "location" not in {key.lower() for key in response.headers}
    return re.search(r'<a href="([^"]+)">Return to', response.text).group(1).replace("&amp;", "&")


# --- Finding 1: navigation is not consent -----------------------------------


def test_get_consent_renders_approval_without_issuing_authority(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", "verifier-a")
        _sign_in(client)

        rendered = client.get(consent_url, follow_redirects=False)
        assert rendered.status_code == 200
        assert "Approve access" in rendered.text
        # No redirect to the client, and therefore no code anywhere in the response.
        assert "location" not in {k.lower() for k in rendered.headers}
        assert "code=" not in rendered.text

        # The pending request survives an arbitrary number of GETs.
        assert client.get(consent_url, follow_redirects=False).status_code == 200


def test_drive_by_get_cannot_steal_authority_for_a_malicious_client(monkeypatch, tmp_path):
    """The original attack, asserted closed.

    A malicious dynamically registered client induces an authenticated user to
    open the consent URL. No code may reach the attacker's redirect URI.
    """
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        client_id = _register(client, ATTACKER_REDIRECT, "Totally Legitimate")
        consent_url = _authorize(client, client_id, ATTACKER_REDIRECT, ATTACKER_VERIFIER)
        _sign_in(client)

        victim = client.get(consent_url, follow_redirects=False)
        assert victim.status_code == 200
        assert "attacker.invalid" not in victim.headers.get("location", "")
        assert "code=" not in victim.text


def test_post_without_csrf_authority_is_refused_and_preserves_pending(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", "verifier-b")
        _sign_in(client)
        request_id = parse_qs(urlparse(consent_url).query)["request"][0]

        missing = client.post("/mcp/consent", data={"request": request_id},
                              follow_redirects=False)
        assert missing.status_code == 403

        forged = client.post("/mcp/consent", follow_redirects=False,
                             data={"request": request_id, "csrf": "not-a-token"})
        assert forged.status_code == 403

        # A CSRF token bound to a different pending request must not approve this one.
        other = _authorize(client, client_id,
                           "https://claude.ai/api/mcp/auth_callback", "verifier-c")
        other_id = parse_qs(urlparse(other).query)["request"][0]
        cfg = webauth.load_config()
        wrong_binding = client.post("/mcp/consent", follow_redirects=False, data={
            "request": request_id,
            "csrf": webauth.csrf_token("remote@example.com", cfg,
                                       f"mcp-consent:{other_id}"),
        })
        assert wrong_binding.status_code == 403

        # None of the refusals consumed the request: approval still works.
        fields = _approval_fields(client.get(consent_url).text)
        approved = client.post("/mcp/consent", data=fields, follow_redirects=False)
        assert urlparse(_completion_target(approved)).hostname == "claude.ai"


def test_explicit_approval_issues_a_single_use_code_and_completes_pkce(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        verifier = "desktop-pkce-verifier"
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", verifier)
        _sign_in(client)

        fields = _approval_fields(client.get(consent_url).text)
        approved = client.post("/mcp/consent", data=fields, follow_redirects=False)
        code = parse_qs(urlparse(_completion_target(approved)).query)["code"][0]

        # Single use: the pending request is gone once it produced a code.
        assert client.get(consent_url, follow_redirects=False).status_code == 400
        assert client.post("/mcp/consent", data=fields,
                           follow_redirects=False).status_code == 400

        # PKCE is still enforced on redemption.
        wrong = client.post("/mcp/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_verifier": "wrong"})
        assert wrong.status_code == 400

        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", verifier)
        fields = _approval_fields(client.get(consent_url).text)
        approved = client.post("/mcp/consent", data=fields, follow_redirects=False)
        code = parse_qs(urlparse(_completion_target(approved)).query)["code"][0]
        token = client.post("/mcp/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_verifier": verifier})
        assert token.status_code == 200
        assert "access_token" in token.json()


def test_unauthenticated_consent_still_redirects_to_login(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", "verifier-d")
        response = client.get(consent_url, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login?return_to=")
        # The pending request survives the login detour.
        _sign_in(client)
        assert client.get(consent_url, follow_redirects=False).status_code == 200


# --- Finding 2: token authority domains -------------------------------------


def test_csrf_token_is_not_a_session(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    cfg = webauth.load_config()
    csrf = webauth.csrf_token("remote@example.com", cfg, "confirm-proposal")
    assert webauth.session_email(csrf, cfg) is None


def test_session_token_is_not_csrf_authority(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    cfg = webauth.load_config()
    session = webauth.session_token("remote@example.com", cfg)
    assert webauth.verify_csrf(session, "remote@example.com", cfg, "confirm-proposal") is False


def test_projection_review_and_pkce_tokens_are_not_sessions(monkeypatch, tmp_path):
    """Both remaining token classes carry state; neither may authenticate."""
    _client(monkeypatch, tmp_path)
    cfg = webauth.load_config()
    projection = webauth.sign(webauth.TYP_PROJECTION_REVIEW, {
        "email": "remote@example.com", "purpose": "pension-projection-review",
        "exp": 2 ** 31}, cfg.session_secret)
    pkce = webauth.sign(webauth.TYP_PKCE, {"v": "verifier", "exp": 2 ** 31},
                        cfg.session_secret)
    assert webauth.session_email(projection, cfg) is None
    assert webauth.session_email(pkce, cfg) is None
    assert webauth.verify_csrf(projection, "remote@example.com", cfg,
                               "pension-projection-review") is False


def test_untyped_legacy_token_is_rejected(monkeypatch, tmp_path):
    """Domain separation fails closed rather than grandfathering old tokens."""
    _client(monkeypatch, tmp_path)
    cfg = webauth.load_config()
    legacy = webauth.sign("", {"email": "remote@example.com", "exp": 2 ** 31},
                          cfg.session_secret)
    assert webauth.session_email(legacy, cfg) is None


def test_legitimate_tokens_still_work_in_their_own_domain(monkeypatch, tmp_path):
    _client(monkeypatch, tmp_path)
    cfg = webauth.load_config()
    assert webauth.session_email(
        webauth.session_token("remote@example.com", cfg), cfg) == "remote@example.com"
    token = webauth.csrf_token("remote@example.com", cfg, "confirm-proposal")
    assert webauth.verify_csrf(token, "remote@example.com", cfg, "confirm-proposal")
    assert webauth.verify_csrf(token, "remote@example.com", cfg, "other-purpose") is False
    assert webauth.verify_csrf(token, "someone@else.com", cfg, "confirm-proposal") is False
    assert webauth.verify_csrf(token + "x", "remote@example.com", cfg,
                               "confirm-proposal") is False


# --- the production-mounted application -------------------------------------


def _production_client(monkeypatch, tmp_path):
    """The real ASGI app, so security-header middleware actually applies.

    The isolated transport harness above mounts `RemoteMcpApplication` alone and
    therefore never sees the middleware that shapes real responses. Anything
    concerning headers must be asserted here instead.
    """
    from foundry.core.entities import declare_party
    from foundry.eventlog import EventLog

    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    for key, value in {
        "FOUNDRY_DATA_PATH": str(log.path), "FOUNDRY_MCP_REMOTE_TOKEN": "remote-test-token",
        "FOUNDRY_MCP_PRINCIPAL": "remote@example.com", "FOUNDRY_MCP_HOUSEHOLD_ID": household.id,
        "FOUNDRY_MCP_CLIENT": "claude-code", "FOUNDRY_WITNESS_MODEL": "claude-sonnet-4-6",
        "APP_BASE_URL": "https://testserver", "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "test-key", "FOUNDRY_ALLOWED_EMAIL": "remote@example.com",
        "SESSION_SECRET": "test-secret",
    }.items():
        monkeypatch.setenv(key, value)

    from fastapi.testclient import TestClient
    from foundry import web

    # The mounted application is a module-level singleton; clear its per-deploy
    # caches so each test builds against its own event log.
    for attribute in ("_application", "_oauth_application",
                      "_oauth_lifespan_application", "_oauth_provider"):
        monkeypatch.setattr(web.remote_mcp_app, attribute, None, raising=False)
    return TestClient(web.app, base_url="https://testserver")


def test_approval_completes_without_a_form_initiated_cross_origin_navigation(
        monkeypatch, tmp_path):
    """Regression for the CSP conflict that blocked completion in Chromium.

    `form-action 'self'` is enforced across a form submission's whole
    navigation chain by Chromium and WebKit but not by Firefox. Answering the
    approval POST with any redirect to the OAuth client is therefore
    browser-dependent. Completion must be offered as a link.
    """
    client = _production_client(monkeypatch, tmp_path)
    with client:
        verifier = "desktop-pkce-verifier"
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", verifier)
        _sign_in(client)

        rendered = client.get(consent_url, follow_redirects=False)
        assert rendered.status_code == 200
        policy = rendered.headers["content-security-policy"]
        assert "form-action 'self'" in policy
        # The form posts same-origin, which is all `form-action 'self'` permits.
        assert re.search(r'<form method="post" action="(/[^"]*)"', rendered.text)

        approved = client.post("/mcp/consent",
                               data=_approval_fields(rendered.text),
                               follow_redirects=False)
        assert approved.status_code == 200
        assert "location" not in {key.lower() for key in approved.headers}
        target = _completion_target(approved)
        assert urlparse(target).hostname == "claude.ai"

        # The code the link carries is real and redeemable.
        code = parse_qs(urlparse(target).query)["code"][0]
        token = client.post("/mcp/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_verifier": verifier})
        assert token.status_code == 200


def test_consent_surfaces_carry_anti_framing_headers_in_production(monkeypatch, tmp_path):
    """Approval is one click, so the page must not be framable."""
    client = _production_client(monkeypatch, tmp_path)
    with client:
        client_id = _register(client, "https://claude.ai/api/mcp/auth_callback", "Claude")
        consent_url = _authorize(client, client_id,
                                 "https://claude.ai/api/mcp/auth_callback", "verifier-e")
        _sign_in(client)

        rendered = client.get(consent_url, follow_redirects=False)
        approved = client.post("/mcp/consent", data=_approval_fields(rendered.text),
                               follow_redirects=False)
        for response in (rendered, approved):
            assert response.headers["x-frame-options"] == "DENY"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"


def test_static_bearer_transport_is_unaffected_in_production(monkeypatch, tmp_path):
    client = _production_client(monkeypatch, tmp_path)
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "Claude Code", "version": "test"}}}
    with client:
        assert client.post("/mcp/", json=initialize,
                           headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.post("/mcp/", json=initialize, headers={
            "Authorization": "Bearer remote-test-token",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18"})
        assert response.status_code == 200
