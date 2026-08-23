"""Narrow OAuth bridge for the remote Foundry MCP boundary.

OAuth establishes the already-configured Foundry principal.  Household
authority remains in the durable Foundry grant checked by CaptureService.
OAuth state intentionally lives only in process memory: it is neither domain
state nor audit/provenance material, and a clean deploy requires re-registering
the connector.
"""

from __future__ import annotations

import html
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode

from mcp.server.auth.provider import AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from foundry import webauth

_ACCESS_TTL = 15 * 60
_CODE_TTL = 5 * 60
_REFRESH_TTL = 12 * 60 * 60


_APPROVAL_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Authorise MCP access</title>
<meta name="robots" content="noindex"></head>
<body>
<main>
<h1>Authorise MCP access</h1>
<p><strong>{client}</strong> is requesting access to this Foundry.</p>
<p>Codes will be returned to: <code>{redirect_uri}</code></p>
<p>Approving grants this client the authority of your Foundry principal.
Only continue if you started this from Claude.</p>
<form method="post" action="/mcp/consent">
<input type="hidden" name="request" value="{request_id}">
<input type="hidden" name="csrf" value="{csrf}">
<button type="submit">Approve access</button>
</form>
<p><a href="/">Cancel</a></p>
</main>
</body></html>"""


_COMPLETION_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Access approved</title>
<meta name="robots" content="noindex"></head>
<body>
<main>
<h1>Access approved</h1>
<p>Approved for <strong>{client}</strong>. Follow the link to finish
connecting; the authorisation expires shortly and can only be used once.</p>
<p><a href="{target}">Return to {client}</a></p>
</main>
</body></html>"""


async def _form_fields(request: Request) -> dict[str, str]:
    """Read an approval submission from the body only.

    Query strings reach browser history, proxies and access logs, and a link
    is exactly the vector this endpoint must not honour.
    """
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        return {}
    try:
        parsed = parse_qs((await request.body()).decode("utf-8"), strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        return {}
    return {key: values[0] for key, values in parsed.items() if len(values) == 1}


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

    def _authorised(self, request: Request, request_id: str):
        """Resolve (pending, cfg, email) or a response explaining the refusal.

        Authentication is settled before the pending request is acknowledged,
        so an unauthenticated caller learns nothing about which request
        identifiers exist.
        """
        cfg = webauth.load_config()
        email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
        if not cfg.allowed_email or email != cfg.allowed_email:
            return_to = f"/mcp/consent?{urlencode({'request': request_id})}"
            return None, None, None, RedirectResponse(
                f"/login?{urlencode({'return_to': return_to})}", status_code=303)
        pending = self.pending.get(request_id)
        if pending is None or pending.expires_at < time.time():
            return None, None, None, HTMLResponse(
                "OAuth request expired. Return to Claude and try again.", status_code=400)
        return pending, cfg, email, None

    @staticmethod
    def consent_purpose(request_id: str) -> str:
        """Bind approval authority to one pending request, not to consent at large."""
        return f"mcp-consent:{request_id}"

    async def consent(self, request: Request):
        """Render the approval surface. Never issues authority."""
        request_id = request.query_params.get("request", "")
        pending, cfg, email, refusal = self._authorised(request, request_id)
        if refusal is not None:
            return refusal
        token = webauth.csrf_token(email, cfg, self.consent_purpose(request_id))
        return HTMLResponse(_APPROVAL_PAGE.format(
            client=html.escape(pending.client.client_name or pending.client.client_id),
            redirect_uri=html.escape(str(pending.params.redirect_uri)),
            request_id=html.escape(request_id, quote=True),
            csrf=html.escape(token, quote=True),
        ))

    async def approve(self, request: Request):
        """Consume the pending request and issue a code. Explicit action only."""
        fields = await _form_fields(request)
        request_id = fields.get("request", "")
        pending, cfg, email, refusal = self._authorised(request, request_id)
        if refusal is not None:
            return refusal
        if not webauth.verify_csrf(fields.get("csrf"), email, cfg,
                                   self.consent_purpose(request_id)):
            # Refusal must not burn a legitimate pending request.
            return HTMLResponse("Approval could not be verified. Return to Claude "
                                "and try again.", status_code=403)
        # Single-use begins here: only a completed approval consumes the request.
        self.pending.pop(request_id, None)
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
        target = f"{pending.params.redirect_uri}{separator}{query}"
        # Completion is a link, not a redirect. Chromium and WebKit enforce the
        # page's `form-action` policy across the whole navigation chain a form
        # submission starts, including onward same-origin hops, so answering
        # this POST with any redirect to the client would be blocked there and
        # allowed in Firefox. Link navigation is not form-initiated, so the
        # completion path is identical in every browser.
        return HTMLResponse(_COMPLETION_PAGE.format(
            client=html.escape(pending.client.client_name or pending.client.client_id),
            target=html.escape(target, quote=True),
        ))

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
