"""RFC-021 Burn 05: the remote transport is authenticated and SDK-native."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from foundry.core.entities import declare_party  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.mcp_remote import RemoteMcpApplication  # noqa: E402


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
    app.mount("/mcp", remote)
    return TestClient(app), household


def test_remote_mcp_fails_closed_then_serves_sdk_initialize(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    }}
    with client:
        assert client.post("/mcp/", json=initialize).status_code == 401
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
