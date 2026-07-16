"""
Minimal web interface. A deployment shell over the substrate, not part
of it: `foundry/__init__.py` does not import this module, so the core
keeps its zero-runtime-dependency invariant. FastAPI is an optional
extra:

    pip install -e ".[web]"
    uvicorn foundry.web:app --host 0.0.0.0 --port 8000

Endpoints:
    GET /health          JSON operational status (public, for Render)
    GET /                HTML status page (requires session)
    GET /login           "Continue with Google" page
    GET /auth/google     starts Supabase Google OAuth (PKCE)
    GET /auth/callback   completes OAuth, sets session, redirects to /
    GET|POST /logout     clears the session
"""

from __future__ import annotations

import ast
import time
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from foundry import __version__
from foundry import webauth

TAGLINE = "Durable organisational intelligence across AI models"

app = FastAPI(title="Foundry", version=__version__, docs_url=None, redoc_url=None)


@lru_cache(maxsize=1)
def _test_count() -> int | None:
    """Count test functions in the repository's tests/ directory.

    Stdlib-only (ast), so the deployed service never needs pytest.
    Returns None when the tests directory isn't shipped alongside the
    package (e.g. a wheel install) — the page then reports it honestly
    rather than inventing a number.
    """
    # web.py -> foundry -> src -> repo root
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    if not tests_dir.is_dir():
        return None
    count = 0
    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    count += 1
    return count


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "foundry", "version": __version__}


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundry V{version}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; background: #faf9f6;
         color: #1a1a1a; max-width: 40rem; margin: 4rem auto; padding: 0 1.5rem;
         line-height: 1.6; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  .tagline {{ color: #555; font-style: italic; margin-top: 0; }}
  .status {{ margin: 2rem 0; padding: 1rem 1.25rem; border-left: 3px solid #2e7d32;
             background: #f1f6f1; }}
  .status strong {{ color: #2e7d32; }}
  dl {{ display: grid; grid-template-columns: max-content auto; gap: 0.3rem 1.5rem; }}
  dt {{ color: #555; }}
  dd {{ margin: 0; }}
  a {{ color: #1a4a8a; }}
  footer {{ margin-top: 3rem; font-size: 0.85rem; color: #777; }}
</style>
</head>
<body>
<h1>Foundry V{version}</h1>
<p class="tagline">{tagline}</p>
<div class="status"><strong>System operational</strong></div>
<dl>
  <dt>Version</dt><dd>{version}</dd>
  <dt>Tests</dt><dd>{tests}</dd>
  <dt>Architecture</dt><dd><a href="{repo}/blob/main/docs/architecture.md">docs/architecture.md</a></dd>
  <dt>Runbook</dt><dd><a href="{repo}/blob/main/docs/RUNBOOK_V1.md">docs/RUNBOOK_V1.md</a></dd>
  <dt>Roadmap</dt><dd><a href="{repo}/blob/main/docs/roadmap.md">docs/roadmap.md</a></dd>
</dl>
<footer>The substrate is sacred; every layer above it is replaceable.</footer>
</body>
</html>
"""

_REPO_URL = "https://github.com/enipeus84/foundry"


@app.get("/", response_class=HTMLResponse)
def status_page(request: Request):
    cfg = webauth.load_config()
    email = webauth.session_email(
        request.cookies.get(webauth.SESSION_COOKIE), cfg)
    if email is None or email != cfg.allowed_email or not cfg.allowed_email:
        return RedirectResponse("/login", status_code=303)
    n = _test_count()
    tests = f"{n} passing" if n is not None else "suite not shipped with this install"
    return HTMLResponse(_PAGE.format(
        version=__version__, tagline=TAGLINE, tests=tests, repo=_REPO_URL))


# --- authentication ----------------------------------------------------------

_LOGIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foundry — sign in</title>
<style>
  body {{ font-family: Georgia, serif; background: #faf9f6; color: #1a1a1a;
         max-width: 24rem; margin: 6rem auto; padding: 0 1.5rem; text-align: center; }}
  h1 {{ font-size: 1.4rem; }}
  a.button {{ display: inline-block; margin-top: 1.5rem; padding: 0.7rem 1.4rem;
              border: 1px solid #1a1a1a; border-radius: 4px; text-decoration: none;
              color: #1a1a1a; background: #fff; }}
  a.button:hover {{ background: #f0efe9; }}
  p.note {{ color: #777; font-size: 0.85rem; margin-top: 2rem; }}
</style></head>
<body>
<h1>Foundry V{version}</h1>
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
    return HTMLResponse(_LOGIN_PAGE.format(version=__version__, note=note))


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
            version=__version__,
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
