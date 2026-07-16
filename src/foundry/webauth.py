"""
Authentication for the web layer. Web-only concern: nothing in the
substrate imports this module.

Design — smallest secure surface:
- Supabase Google OAuth via the PKCE flow. The code verifier travels in
  a short-lived signed cookie; the callback exchanges the auth code
  server-side, so tokens never appear in URLs the browser retains.
- Sessions are stateless, HMAC-SHA256-signed cookies (stdlib only):
  base64url(payload).base64url(signature), payload = {email, exp}.
  No session store to run, nothing to leak at rest.
- Fail closed: missing configuration rejects everyone rather than
  admitting anyone.

Configuration (environment variables, never source code):
    SUPABASE_URL              e.g. https://xyz.supabase.co
    SUPABASE_PUBLISHABLE_KEY  the publishable (anon) API key
    FOUNDRY_ALLOWED_EMAIL     the single permitted Google account
    SESSION_SECRET            >= 32 random bytes, e.g. `openssl rand -hex 32`
    APP_BASE_URL              e.g. https://foundry.onrender.com
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass

import httpx

SESSION_COOKIE = "foundry_session"
VERIFIER_COOKIE = "foundry_pkce"
SESSION_TTL = 12 * 3600          # seconds
VERIFIER_TTL = 10 * 60


@dataclass(frozen=True)
class AuthConfig:
    supabase_url: str
    publishable_key: str
    allowed_email: str
    session_secret: bytes
    app_base_url: str
    secure_cookies: bool

    @property
    def configured(self) -> bool:
        return all((self.supabase_url, self.publishable_key,
                    self.allowed_email, self.session_secret))


def load_config() -> AuthConfig:
    """Read config from the environment on every call — testable, and
    no import-order trap where env vars set late are silently missed."""
    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    return AuthConfig(
        supabase_url=os.environ.get("SUPABASE_URL", "").rstrip("/"),
        publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
        allowed_email=os.environ.get("FOUNDRY_ALLOWED_EMAIL", "").strip().lower(),
        session_secret=os.environ.get("SESSION_SECRET", "").encode(),
        app_base_url=base,
        secure_cookies=base.startswith("https://"),
    )


# --- signed tokens (stdlib) -------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign(payload: dict, secret: bytes) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str, secret: bytes) -> dict | None:
    """Return the payload if the signature is valid and unexpired."""
    if not secret or not token or token.count(".") != 1:
        return None
    body, sig = token.split(".")
    expected = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, UnicodeDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def session_token(email: str, cfg: AuthConfig) -> str:
    return sign({"email": email, "exp": int(time.time()) + SESSION_TTL},
                cfg.session_secret)


def session_email(token: str | None, cfg: AuthConfig) -> str | None:
    if token is None:
        return None
    payload = verify(token, cfg.session_secret)
    return payload.get("email") if payload else None


# --- Supabase PKCE flow -----------------------------------------------------

def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def authorize_url(cfg: AuthConfig, challenge: str) -> str:
    return (
        f"{cfg.supabase_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={cfg.app_base_url}/auth/callback"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=s256"
    )


def exchange_code(cfg: AuthConfig, code: str, verifier: str) -> str | None:
    """Exchange the auth code for the user's email. Returns None on any
    failure — the caller treats None as 'not authenticated'."""
    try:
        r = httpx.post(
            f"{cfg.supabase_url}/auth/v1/token?grant_type=pkce",
            headers={"apikey": cfg.publishable_key},
            json={"auth_code": code, "code_verifier": verifier},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        email = (r.json().get("user") or {}).get("email")
        return email.strip().lower() if email else None
    except httpx.HTTPError:
        return None
