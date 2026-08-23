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
from urllib.parse import urlsplit

import httpx

SESSION_COOKIE = "foundry_session"
VERIFIER_COOKIE = "foundry_pkce"
SESSION_TTL = 12 * 3600          # seconds
VERIFIER_TTL = 10 * 60
CSRF_TTL = 10 * 60

# Token authority domains. One signing key, but a token is only ever valid in
# the domain it was issued for. Add a constant here before minting a new class.
TYP_SESSION = "session"
TYP_CSRF = "csrf"
TYP_PKCE = "pkce"
TYP_PROJECTION_REVIEW = "projection-review"


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


def local_return_path(value: str | None) -> str | None:
    """Accept only an origin-local absolute path for post-login redirects."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    return value


# --- signed tokens (stdlib) -------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign(typ: str, payload: dict, secret: bytes) -> str:
    """Sign a payload into a single token authority domain.

    Every token carries its issuing domain in `typ`. A signature alone is not
    authority: verification requires the caller to name the domain it expects,
    so a token minted for one purpose cannot be replayed as another.
    """
    body = _b64(json.dumps({**payload, "typ": typ},
                           separators=(",", ":"), sort_keys=True).encode())
    sig = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(typ: str, token: str, secret: bytes) -> dict | None:
    """Return the payload if signature, domain and expiry all hold.

    Fails closed on an absent or mismatched `typ`, so a token issued before
    domain separation existed is not silently honoured.
    """
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
    if not isinstance(payload, dict):
        return None
    if not hmac.compare_digest(str(payload.get("typ", "")), typ):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def session_token(email: str, cfg: AuthConfig) -> str:
    return sign(TYP_SESSION, {"email": email, "exp": int(time.time()) + SESSION_TTL},
                cfg.session_secret)


def session_email(token: str | None, cfg: AuthConfig) -> str | None:
    if token is None:
        return None
    payload = verify(TYP_SESSION, token, cfg.session_secret)
    return payload.get("email") if payload else None


def csrf_token(email: str, cfg: AuthConfig, purpose: str) -> str:
    """A short-lived, signed, same-user CSRF token for a state-changing form."""
    return sign(TYP_CSRF, {"email": email, "purpose": purpose,
                           "exp": int(time.time()) + CSRF_TTL}, cfg.session_secret)


def verify_csrf(token: str | None, email: str, cfg: AuthConfig, purpose: str) -> bool:
    payload = verify(TYP_CSRF, token or "", cfg.session_secret)
    return bool(payload and payload.get("email") == email and payload.get("purpose") == purpose)


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
