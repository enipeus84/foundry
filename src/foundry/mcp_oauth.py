"""Narrow OAuth bridge for the remote Foundry MCP boundary.

OAuth establishes the already-configured Foundry principal.  Household
authority remains in the durable Foundry grant checked by CaptureService.
OAuth state intentionally lives only in process memory: it is neither domain
state nor audit/provenance material, and a clean deploy requires re-registering
the connector.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from mcp.server.auth.provider import AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from foundry import webauth

_ACCESS_TTL = 15 * 60
_CODE_TTL = 5 * 60
_REFRESH_TTL = 12 * 60 * 60


@dataclass
class _Pending:
    client: OAuthClientInformationFull
    params: AuthorizationParams
    expires_at: float


class FoundryOAuthProvider:
    """Single-principal, PKCE-only provider used by the MCP SDK routes."""

    def __init__(self, consent_url: str = "consent") -> None:
        self.consent_url = consent_url
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.pending: dict[str, _Pending] = {}
        self.codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # The SDK has already validated the registration schema.  Credentials
        # expire at deploy by design; no client secret is persisted in Foundry.
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        request_id = secrets.token_urlsafe(32)
        self.pending[request_id] = _Pending(client, params, time.time() + _CODE_TTL)
        return f"{self.consent_url}?{urlencode({'request': request_id})}"

    async def consent(self, request: Request):
        request_id = request.query_params.get("request", "")
        pending = self.pending.pop(request_id, None)
        cfg = webauth.load_config()
        email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
        if pending is None or pending.expires_at < time.time():
            return HTMLResponse("OAuth request expired. Return to Claude and try again.", status_code=400)
        if email != cfg.allowed_email:
            return RedirectResponse("/login", status_code=303)
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=pending.params.scopes or [], expires_at=time.time() + _CODE_TTL,
            client_id=pending.client.client_id, code_challenge=pending.params.code_challenge,
            redirect_uri=pending.params.redirect_uri,
            redirect_uri_provided_explicitly=pending.params.redirect_uri_provided_explicitly,
            resource=pending.params.resource, subject=email,
        )
        separator = "&" if "?" in str(pending.params.redirect_uri) else "?"
        query = urlencode({"code": code, **({"state": pending.params.state} if pending.params.state else {})})
        return RedirectResponse(f"{pending.params.redirect_uri}{separator}{query}", status_code=302)

    async def load_authorization_code(self, client, authorization_code):
        code = self.codes.pop(authorization_code, None)
        return code if code and code.client_id == client.client_id and code.expires_at >= time.time() else None

    async def exchange_authorization_code(self, client, authorization_code):
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.subject,
                           authorization_code.resource)

    async def load_refresh_token(self, client, refresh_token):
        value = self.refresh_tokens.pop(refresh_token, None)
        return value if value and value.client_id == client.client_id else None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        if refresh_token.expires_at and refresh_token.expires_at < time.time():
            raise ValueError("refresh token expired")
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.subject, None)

    async def load_access_token(self, token: str):
        value = self.tokens.get(token)
        return value if value and (value.expires_at or 0) >= time.time() else None

    def _issue(self, client_id: str, scopes: list[str], subject: str | None, resource: str | None) -> OAuthToken:
        token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        self.tokens[token] = AccessToken(token=token, client_id=client_id, scopes=scopes,
                                         expires_at=int(time.time() + _ACCESS_TTL), subject=subject,
                                         resource=resource)
        self.refresh_tokens[refresh_token] = RefreshToken(
            token=refresh_token, client_id=client_id, scopes=scopes,
            expires_at=int(time.time() + _REFRESH_TTL), subject=subject)
        return OAuthToken(access_token=token, refresh_token=refresh_token,
                          expires_in=_ACCESS_TTL, scope=" ".join(scopes))
