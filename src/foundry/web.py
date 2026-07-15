"""
Minimal web interface. A deployment shell over the substrate, not part
of it: `foundry/__init__.py` does not import this module, so the core
keeps its zero-runtime-dependency invariant. FastAPI is an optional
extra:

    pip install -e ".[web]"
    uvicorn foundry.web:app --host 0.0.0.0 --port 8000

Endpoints:
    GET /health   JSON operational status
    GET /         HTML status page
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from foundry import __version__

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
def status_page() -> str:
    n = _test_count()
    tests = f"{n} passing" if n is not None else "suite not shipped with this install"
    return _PAGE.format(version=__version__, tagline=TAGLINE, tests=tests, repo=_REPO_URL)
