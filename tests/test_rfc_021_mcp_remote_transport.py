"""RFC-021 Burn 05: the remote transport is authenticated and SDK-native."""

from __future__ import annotations

from contextlib import asynccontextmanager
import base64
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from foundry.core.entities import declare_party  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.mcp_remote import McpCanonicalPath, RemoteMcpApplication  # noqa: E402
from foundry import webauth  # noqa: E402


def _approve(client, consent_url):
    """Explicit approval: GET renders the form, POST returns the completion link.

    Completion is a link rather than a redirect so that the page's CSP
    `form-action` policy cannot block it in Chromium or WebKit.
    """
    rendered = client.get(consent_url, follow_redirects=False)
    assert rendered.status_code == 200
    fields = dict(re.findall(r'name="(\w+)" value="([^"]+)"', rendered.text))
    approved = client.post("/mcp/consent", data=fields, follow_redirects=False)
    assert approved.status_code == 200
    assert "location" not in {key.lower() for key in approved.headers}
    return re.search(r'<a href="([^"]+)">Return to', approved.text).group(1).replace("&amp;", "&")


def _client(monkeypatch, tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(log.path))
    monkeypatch.setenv("FOUNDRY_MCP_REMOTE_TOKEN", "remote-test-token")
    monkeypatch.setenv("FOUNDRY_MCP_PRINCIPAL", "remote@example.com")
    monkeypatch.setenv("FOUNDRY_MCP_HOUSEHOLD_ID", household.id)
    monkeypatch.setenv("FOUNDRY_MCP_CLIENT", "claude-code")
    monkeypatch.setenv("FOUNDRY_WITNESS_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("APP_BASE_URL", "https://testserver")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", "remote@example.com")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    remote = RemoteMcpApplication()

    @asynccontextmanager
    async def lifespan(_):
        async with remote.lifespan():
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(McpCanonicalPath)
    app.mount("/mcp", remote)
    return TestClient(app), household


def test_remote_mcp_fails_closed_then_serves_sdk_initialize(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    }}
    with client:
        challenge = client.post("/mcp", json=initialize, follow_redirects=False)
        assert challenge.status_code == 401
        assert challenge.headers["www-authenticate"] == (
            'Bearer error="invalid_token", error_description="Authentication required", '
            'resource_metadata="https://testserver/.well-known/oauth-protected-resource/mcp"')
        assert client.post("/mcp/", headers={"Authorization": "Bearer wrong"},
                           json=initialize).status_code == 401
        response = client.post("/mcp/", headers={
            "Authorization": "Bearer remote-test-token",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        }, json=initialize)
    assert response.status_code == 200
    message = next(line.removeprefix("data: ") for line in response.text.splitlines()
                   if line.startswith("data: "))
    assert json.loads(message)["result"]["serverInfo"]["name"] == "Foundry"


def test_render_build_installs_web_and_mcp_extras():
    manifest = Path(__file__).parents[1] / "render.yaml"
    assert 'buildCommand: pip install -e ".[web,mcp]"' in manifest.read_text()


def test_desktop_oauth_registration_pkce_and_mcp_access(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    registration = {
        "client_name": "Claude",
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    with client:
        metadata = client.get("/mcp/.well-known/oauth-authorization-server")
        assert metadata.status_code == 200
        assert metadata.json()["code_challenge_methods_supported"] == ["S256"]
        assert "none" in metadata.json()["token_endpoint_auth_methods_supported"]
        registered = client.post("/mcp/register", json=registration)
        assert registered.status_code == 201
        assert registered.json()["client_name"] == "Claude"
        assert registered.json()["redirect_uris"] == ["https://claude.ai/api/mcp/auth_callback"]
        assert registered.json()["token_endpoint_auth_method"] == "none"
        client_id = registered.json()["client_id"]
        bad = client.get("/mcp/authorize", params={
            "client_id": client_id, "response_type": "code", "code_challenge": "challenge",
            "code_challenge_method": "S256", "redirect_uri": "https://attacker.invalid/callback",
        })
        assert bad.status_code == 400
        client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
            "remote@example.com", webauth.load_config()))
        verifier = "desktop-pkce-verifier"
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        authorize = client.get("/mcp/authorize", params={
            "client_id": client_id, "response_type": "code", "code_challenge": challenge,
            "code_challenge_method": "S256", "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "state": "state-value",
        }, follow_redirects=False)
        assert authorize.status_code == 302
        # Navigation alone must not produce authority.
        navigated = client.get(authorize.headers["location"], follow_redirects=False)
        assert navigated.status_code == 200
        assert "code=" not in navigated.text
        callback = urlparse(_approve(client, authorize.headers["location"]))
        assert callback.hostname == "claude.ai"
        query = parse_qs(callback.query)
        assert query["state"] == ["state-value"]
        token = client.post("/mcp/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": query["code"][0],
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback", "code_verifier": "wrong",
        })
        assert token.status_code == 400
        authorize = client.get("/mcp/authorize", params={
            "client_id": client_id, "response_type": "code", "code_challenge": challenge,
            "code_challenge_method": "S256", "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        }, follow_redirects=False)
        code = parse_qs(urlparse(_approve(client, authorize.headers["location"])).query)["code"][0]
        token = client.post("/mcp/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback", "code_verifier": verifier,
        })
        assert token.status_code == 200
        access_token = token.json()["access_token"]
        assert "refresh_token" in token.json()
        initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Claude Desktop", "version": "test"},
        }}
        response = client.post("/mcp/", headers={
            "Authorization": f"Bearer {access_token}", "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json", "MCP-Protocol-Version": "2025-06-18",
        }, json=initialize)
        assert response.status_code == 200


def test_google_login_resumes_mcp_consent_and_loads_existing_tools(monkeypatch, tmp_path):
    """The MCP request survives Google login and is consumed at code issuance."""
    from foundry import web

    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(log.path))
    monkeypatch.setenv("FOUNDRY_MCP_REMOTE_TOKEN", "remote-test-token")
    monkeypatch.setenv("FOUNDRY_MCP_PRINCIPAL", "remote@example.com")
    monkeypatch.setenv("FOUNDRY_MCP_HOUSEHOLD_ID", household.id)
    monkeypatch.setenv("FOUNDRY_MCP_CLIENT", "claude-code")
    monkeypatch.setenv("FOUNDRY_WITNESS_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("APP_BASE_URL", "https://testserver")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", "remote@example.com")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setattr(webauth, "exchange_code", lambda cfg, code, verifier: "remote@example.com")
    verifier = "desktop-pkce-verifier"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    registration = {"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                    "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"]}
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "Claude", "version": "test"}}}
    remote = RemoteMcpApplication()

    @asynccontextmanager
    async def lifespan(_):
        async with remote.lifespan():
            yield

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(McpCanonicalPath)
    app.add_api_route("/login", web.login, methods=["GET"])
    app.add_api_route("/auth/google", web.auth_google, methods=["GET"])
    app.add_api_route("/auth/callback", web.auth_callback, methods=["GET"])
    app.mount("/mcp", remote)
    with TestClient(app, base_url="https://testserver") as client:
        registered = client.post("/mcp/register", json=registration)
        assert registered.status_code == 201, registered.text
        client_id = registered.json()["client_id"]
        authorize = client.get("/mcp/authorize", params={
            "client_id": client_id, "response_type": "code", "code_challenge": challenge,
            "code_challenge_method": "S256", "redirect_uri": "https://claude.ai/api/mcp/auth_callback"},
            follow_redirects=False)
        consent = client.get(authorize.headers["location"], follow_redirects=False)
        assert consent.headers["location"].startswith("/login?return_to=")
        login = client.get(consent.headers["location"], follow_redirects=False)
        auth_google = re.search(r'href="([^"]+)"', login.text).group(1).replace("&amp;", "&")
        client.get(auth_google, follow_redirects=False)
        callback = client.get("/auth/callback?code=fake", follow_redirects=False)
        redirect = _approve(client, callback.headers["location"])
        code = parse_qs(urlparse(redirect).query)["code"][0]
        assert client.get(callback.headers["location"], follow_redirects=False).status_code == 400
        token = client.post("/mcp/token", data={"grant_type": "authorization_code", "client_id": client_id,
                            "code": code, "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                            "code_verifier": verifier})
        assert token.status_code == 200
        headers = {"Authorization": f"Bearer {token.json()['access_token']}",
                   "Accept": "application/json, text/event-stream", "Content-Type": "application/json",
                   "MCP-Protocol-Version": "2025-06-18"}
        initialized = client.post("/mcp/", headers=headers, json=initialize)
        assert initialized.status_code == 200
        headers["Mcp-Session-Id"] = initialized.headers["mcp-session-id"]
        tools = client.post("/mcp/", headers=headers, json={"jsonrpc": "2.0", "id": 2,
                            "method": "tools/list", "params": {}})
    assert tools.status_code == 200
    message = next(line.removeprefix("data: ") for line in tools.text.splitlines() if line.startswith("data: "))
    # OAuth exposes the same registry, including the Pension commissioning slice.
    assert len(json.loads(message)["result"]["tools"]) == 25


def test_oauth_discovery_bypasses_static_bearer_guard_without_feature_flag(monkeypatch, tmp_path):
    """Regression: deployed Burn 06 returned 401 before OAuth discovery."""
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        assert client.get("/mcp/.well-known/oauth-authorization-server").status_code == 200


def test_protected_resource_metadata_is_public_without_feature_flag(monkeypatch):
    """Regression: deployed Burn 06 returned 404 at the RFC 9728 path."""
    from foundry.web import app

    monkeypatch.setenv("APP_BASE_URL", "https://foundry.example")
    monkeypatch.delenv("FOUNDRY_MCP_OAUTH_ENABLED", raising=False)
    with TestClient(app) as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://foundry.example/mcp"


def test_claude_discovery_follows_rfc8414_issuer_path_metadata(monkeypatch, tmp_path):
    """Regression: Claude looked up /.well-known/oauth-authorization-server/mcp."""
    from foundry.web import app

    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(log.path))
    monkeypatch.setenv("FOUNDRY_MCP_REMOTE_TOKEN", "remote-test-token")
    monkeypatch.setenv("FOUNDRY_MCP_PRINCIPAL", "remote@example.com")
    monkeypatch.setenv("FOUNDRY_MCP_HOUSEHOLD_ID", household.id)
    monkeypatch.setenv("FOUNDRY_MCP_CLIENT", "claude-code")
    monkeypatch.setenv("FOUNDRY_WITNESS_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("APP_BASE_URL", "https://foundry.example")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", "remote@example.com")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "Claude Desktop", "version": "test"},
    }}

    with TestClient(app) as client:
        challenge = client.post("/mcp", json=initialize, follow_redirects=False)
        assert challenge.status_code == 401
        resource_metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert resource_metadata.status_code == 200
        assert resource_metadata.json()["authorization_servers"] == ["https://foundry.example/mcp"]
        authorization_metadata = client.get("/.well-known/oauth-authorization-server/mcp")

    assert authorization_metadata.status_code == 200
    assert authorization_metadata.json() == {
        "issuer": "https://foundry.example/mcp",
        "authorization_endpoint": "https://foundry.example/mcp/authorize",
        "token_endpoint": "https://foundry.example/mcp/token",
        "registration_endpoint": "https://foundry.example/mcp/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
    }
