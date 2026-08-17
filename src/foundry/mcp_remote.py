"""Bearer-protected Streamable HTTP transport for the existing Foundry MCP server."""

from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from typing import Awaitable, Callable
from urllib.parse import urlparse

from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

from foundry.application.mcp_context import McpPrincipal, query_for_mcp_principal, remote_principal_from_environment
from foundry.mcp_oauth import FoundryOAuthProvider
from foundry.mcp_server import create_mcp_server


_ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]


def _transport_security() -> tuple[str, TransportSecuritySettings]:
    base_url = os.environ.get("APP_BASE_URL", "")
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise PermissionError("Foundry remote MCP requires APP_BASE_URL")
    return parsed.hostname or parsed.netloc, TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[parsed.netloc],
        allowed_origins=[base_url],
    )


class RemoteMcpApplication:
    """A fixed single-principal transport; credentials never enter tool arguments."""

    def __init__(self):
        self._application: _ASGIApp | None = None
        self._oauth_application: _ASGIApp | None = None
        self._oauth_provider: FoundryOAuthProvider | None = None

    def _application_for_request(self) -> _ASGIApp:
        if self._application is None:
            principal = remote_principal_from_environment()
            host, transport_security = _transport_security()
            server = create_mcp_server(
                query_for_mcp_principal(principal), principal, streamable_http_path="/",
                host=host, transport_security=transport_security)
            self._application = server.streamable_http_app()
        return self._application

    def _oauth_application_for_request(self) -> _ASGIApp:
        """Build the Desktop-only adapter; its tools retain Foundry authority."""
        if self._oauth_application is None:
            principal = remote_principal_from_environment()
            host, transport_security = _transport_security()
            base_url = os.environ["APP_BASE_URL"].rstrip("/")
            self._oauth_provider = FoundryOAuthProvider(f"{base_url}/mcp/consent")
            desktop = McpPrincipal(principal.email, principal.household_id,
                                   "claude-desktop", principal.witness_model)
            server = create_mcp_server(
                query_for_mcp_principal(desktop), desktop, streamable_http_path="/", host=host,
                transport_security=transport_security, auth=AuthSettings(
                    issuer_url=f"{base_url}/mcp", resource_server_url=f"{base_url}/mcp",
                    required_scopes=[], client_registration_options=ClientRegistrationOptions(enabled=True),
                ), auth_server_provider=self._oauth_provider)

            @server.custom_route("/consent", methods=["GET"])
            async def consent(request):
                return await self._oauth_provider.consent(request)

            self._oauth_application = server.streamable_http_app()
        return self._oauth_application

    @asynccontextmanager
    async def lifespan(self):
        """Start the SDK session manager only when remote MCP is configured."""
        if not os.environ.get("FOUNDRY_MCP_REMOTE_TOKEN"):
            yield
            return
        application = self._application_for_request()
        async with application.router.lifespan_context(application):
            if os.environ.get("FOUNDRY_MCP_OAUTH_ENABLED") == "true":
                oauth_application = self._oauth_application_for_request()
                async with oauth_application.router.lifespan_context(oauth_application):
                    yield
            else:
                yield

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._refuse(send, 404)
            return
        credential = os.environ.get("FOUNDRY_MCP_REMOTE_TOKEN")
        authorization = dict(scope.get("headers", [])).get(b"authorization", b"").decode("latin-1")
        if not credential:
            await self._refuse(send, 401)
            return
        try:
            if authorization.startswith("Bearer ") and hmac.compare_digest(
                    authorization.removeprefix("Bearer "), credential):
                await self._application_for_request()(scope, receive, send)
            elif os.environ.get("FOUNDRY_MCP_OAUTH_ENABLED") == "true":
                await self._oauth_application_for_request()(scope, receive, send)
            else:
                await self._refuse(send, 401)
        except PermissionError:
            await self._refuse(send, 503)

    @staticmethod
    async def _refuse(send, status: int) -> None:
        headers = [(b"content-type", b"application/json")]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b'{"error":"MCP access refused"}'})


remote_mcp_app = RemoteMcpApplication()
