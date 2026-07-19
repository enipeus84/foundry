"""
The web application — Mission Control's composition root. A deployment
shell over the substrate, not part of it: `foundry/__init__.py` does
not import this module, so the core keeps its zero-runtime-dependency
invariant. FastAPI is an optional extra:

    pip install -e ".[web]"
    uvicorn foundry.web:app --host 0.0.0.0 --port 8000

Endpoints:
    GET /health           JSON operational status (public, for Render)
    GET /                 Mission Control home (requires session)
    GET /metrics/{id}     KPI drill-down (requires session)
    GET /finance|/decisions|/missions|/settings   placeholders
    GET /login            "Continue with Google" page
    GET /auth/google      starts Supabase Google OAuth (PKCE)
    GET /auth/callback    completes OAuth, sets session, redirects to /
    GET|POST /logout      clears the session

**This module is the one place Finance meets Core** (RFC-003's rule:
Mission Control never imports a domain's calculation code — so the
composition root does the wiring instead, exactly as
examples/finance_demo.py does for the CLI). `_build_console()` reads
the event log named by FOUNDRY_DATA_PATH, folds the projections, and
registers the Finance provider with a fresh Metric Registry. Mission
Control receives the finished `Console` and composes; it cannot reach
Finance any other way.

Configuration:
    FOUNDRY_DATA_PATH    path to the events.jsonl to serve
                         (default: foundry_data/events.jsonl —
                         seed one with examples/seed_mission_control.py)
    + the auth variables documented in webauth.py
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from foundry import __version__
from foundry import webauth
from foundry.canon import Canon
from foundry.core.entities import EntityProjection
from foundry.core.evidence import EvidenceIndex
from foundry.core.metrics import MetricRegistry
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.mission_control import Console, router as mission_control_router

app = FastAPI(title="Foundry", version=__version__, docs_url=None, redoc_url=None)

DEFAULT_DATA_PATH = "foundry_data/events.jsonl"


def _build_console() -> Console:
    """Fresh projections over the configured log, with the Finance
    provider registered — rebuilt per request so the page always
    reflects the log as it is now. Replay of these logs is milliseconds;
    incremental maintenance is an optimisation for a later RFC."""
    log = EventLog(os.environ.get("FOUNDRY_DATA_PATH", DEFAULT_DATA_PATH))
    core_entities = EntityProjection(log)
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(FinanceEntityProjection(log), core_entities))
    return Console(log=log, registry=registry, entities=core_entities,
                   evidence=EvidenceIndex(log), canon=Canon(log))


app.state.console_factory = _build_console
app.include_router(mission_control_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Public-internet hardening for a zero-JS, inline-styled surface:
    the CSP permits exactly what the pages use and nothing else.
    /health stays cacheable for the platform's health checker; every
    authenticated page is no-store."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'self'")
    if request.url.path != "/health":
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "foundry", "version": __version__}


# --- authentication ----------------------------------------------------------

_LOGIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundry — sign in</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #0b0e12; color: #e6edf3; max-width: 24rem; margin: 6rem auto;
         padding: 0 1.5rem; text-align: center; }}
  .mark {{ font-size: 1.6rem; }}
  h1 {{ font-size: .8rem; letter-spacing: .24em; color: #7d8894; font-weight: 600;
        margin-top: .8rem; }}
  a.button {{ display: inline-block; margin-top: 2rem; padding: 0.7rem 1.4rem;
              border: 1px solid #2b3440; border-radius: 6px; text-decoration: none;
              color: #e6edf3; background: #10141a; }}
  a.button:hover {{ border-color: #4d5661; }}
  p.note {{ color: #4d5661; font-size: 0.85rem; margin-top: 2rem; }}
</style></head>
<body>
<div class="mark">◈</div>
<h1>FOUNDRY · MISSION CONTROL</h1>
<a class="button" href="/auth/google">Continue with Google</a>
<p class="note">{note}</p>
</body></html>
"""


def _cookie(resp: Response, name: str, value: str, max_age: int,
            secure: bool) -> None:
    resp.set_cookie(name, value, max_age=max_age, httponly=True,
                    samesite="lax", secure=secure, path="/")


@app.get("/login", response_class=HTMLResponse)
def login():
    cfg = webauth.load_config()
    note = ("Access restricted to the authorised account."
            if cfg.configured else
            "Authentication is not configured on this deployment.")
    return HTMLResponse(_LOGIN_PAGE.format(note=note))


@app.get("/auth/google")
def auth_google():
    cfg = webauth.load_config()
    if not cfg.configured:
        return RedirectResponse("/login", status_code=303)
    verifier, challenge = webauth.pkce_pair()
    resp = RedirectResponse(webauth.authorize_url(cfg, challenge),
                            status_code=303)
    # Verifier travels signed so it can't be tampered with in transit.
    _cookie(resp, webauth.VERIFIER_COOKIE,
            webauth.sign({"v": verifier,
                          "exp": int(time.time()) + webauth.VERIFIER_TTL},
                         cfg.session_secret),
            webauth.VERIFIER_TTL, cfg.secure_cookies)
    return resp


@app.get("/auth/callback")
def auth_callback(request: Request, code: str | None = None):
    cfg = webauth.load_config()
    if not cfg.configured or code is None:
        return RedirectResponse("/login", status_code=303)
    packed = webauth.verify(
        request.cookies.get(webauth.VERIFIER_COOKIE, ""), cfg.session_secret)
    if not packed:
        return RedirectResponse("/login", status_code=303)
    email = webauth.exchange_code(cfg, code, packed["v"])
    resp: Response
    if email is None or email != cfg.allowed_email:
        # Authenticated with Google, but not the permitted account.
        resp = HTMLResponse(_LOGIN_PAGE.format(
            note="This Google account is not authorised for this Foundry."),
            status_code=403)
    else:
        resp = RedirectResponse("/", status_code=303)
        _cookie(resp, webauth.SESSION_COOKIE,
                webauth.session_token(email, cfg),
                webauth.SESSION_TTL, cfg.secure_cookies)
    resp.delete_cookie(webauth.VERIFIER_COOKIE, path="/")
    return resp


@app.get("/logout")
@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(webauth.SESSION_COOKIE, path="/")
    return resp
