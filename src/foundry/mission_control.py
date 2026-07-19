"""
Mission Control v0.1 — the first real product surface (RFC-003).

A read-only composition layer over Core's contracts. The division of
responsibility is architectural, not stylistic:

    Finance calculates.   (foundry.finance — never imported here)
    Core evaluates.       (mission_evaluation, compose_tile)
    Mission Control composes.   (this module — no business logic)

Everything on every page arrives through exactly two Core contracts:
the Metric Registry (`registry.dispatch`, 000 §13) and the Flight Deck
tile contract (`compose_tile`, 000 §14). This module never calculates
a figure, never owns state, never appends an event, and never imports
a domain's calculation code — the AST test in
tests/test_mission_control.py enforces that last property structurally.

The app's composition root (web.py) supplies a `Console` factory via
`app.state.console_factory`; that factory — not this module — is where
domain providers get registered with the registry. Rebuilt fresh per
request: projections are cheap folds, and a page rendered twice from
the same log is byte-identical (the determinism test), because `as_of`
is the latest event's timestamp, not the wall clock.

Design (RFC-003): calm, sparse, high-signal, dark-first, typography
over chrome. Server-rendered HTML, zero JavaScript, zero new
dependencies.
"""

from __future__ import annotations

import ast
import html
import json
import os
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from foundry import __version__
from foundry import webauth
from foundry.canon import Canon
from foundry.core.entities import EntityProjection, Mission
from foundry.core.evidence import EvidenceIndex
from foundry.core.flight_deck import Tile, compose_tile
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.mission_evaluation import get_mission_status
from foundry.core.scope import Subject
from foundry.eventlog import EventLog

router = APIRouter()


@dataclass
class Console:
    """Everything a page render needs, built by the composition root
    (web.py) — Mission Control itself constructs none of the domain
    wiring and registers nothing with the registry."""
    log: EventLog
    registry: MetricRegistry
    entities: EntityProjection
    evidence: EvidenceIndex
    canon: Canon


# The five opening-screen KPIs (RFC-003). Metric identifiers are the
# registry's public contract (000 §13.1) — strings, not imports.
KPI_CARDS: tuple[tuple[str, str, str], ...] = (
    ("NET WORTH", "finance.net_worth", "currency"),
    ("LIQUIDITY RUNWAY", "finance.liquidity_runway", "months"),
    ("EMPLOYER CONCENTRATION", "finance.employer_concentration", "percent"),
    ("DEBT RATIO", "finance.debt_ratio", "percent"),
    ("CASH AVAILABLE", "finance.cash_available", "currency"),
)

_RAG_TO_BANNER = {
    "on_track": ("GREEN", "green"),
    "achieved": ("GREEN", "green"),
    "at_risk": ("AMBER", "amber"),
    "off_track": ("RED", "red"),
}


# ------------------------------------------------------------------ session

def session_email(request: Request) -> str | None:
    """The exact fail-closed check the status page used: a valid signed
    session for the single allowed account, or nothing."""
    cfg = webauth.load_config()
    email = webauth.session_email(request.cookies.get(webauth.SESSION_COOKIE), cfg)
    if email is None or not cfg.allowed_email or email != cfg.allowed_email:
        return None
    return email


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def _console(request: Request) -> Console:
    return request.app.state.console_factory()


# ------------------------------------------------------------------ helpers

def _as_of(console: Console) -> float:
    """The latest observation's timestamp — 'the data speaks as of the
    last thing it saw', which is also what makes rendering
    deterministic for a given log (no wall clock in any value)."""
    last = 0.0
    for e in console.log.events():
        last = e["ts"]
    return last


def _household_scope(console: Console) -> Subject | None:
    """The most recently declared active household Party — Mission
    Control's v0.1 top-level scope. Multi-household selection is a
    Settings concern for a later RFC."""
    households = [p for p in console.entities.parties.values()
                  if p.party_type == "household" and p.status == "active"]
    return Subject("party", households[-1].id) if households else None


def _current_mission(console: Console) -> Mission | None:
    active = [m for m in console.entities.missions.values() if m.status == "active"]
    return active[-1] if active else None


_CURRENCY_SYMBOL = {"GBP": "£", "USD": "$", "EUR": "€"}


def _format_value(value: float | None, unit: str | None, kind: str) -> str:
    if value is None:
        return "—"
    if kind == "currency":
        symbol = _CURRENCY_SYMBOL.get(unit or "", f"{unit} " if unit else "")
        return f"{symbol}{value:,.0f}"
    if kind == "percent":
        return f"{value * 100:.1f}%"
    if kind == "months":
        return f"{value:.1f} mo"
    return f"{value:,.2f}"


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts)) if ts else "—"


@lru_cache(maxsize=1)
def _test_count() -> int | None:
    """Live test-function count via stdlib ast (no pytest at runtime).
    None when the tests directory isn't shipped with this install —
    reported honestly rather than invented."""
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    if not tests_dir.is_dir():
        return None
    count = 0
    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count += sum(1 for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name.startswith("test_"))
    return count


@lru_cache(maxsize=1)
def _git_commit() -> str:
    """Short commit hash: env first (Render exposes RENDER_GIT_COMMIT;
    generic deploys may set GIT_COMMIT), then a local `git rev-parse`,
    else 'unknown' — never a fabricated value."""
    for var in ("RENDER_GIT_COMMIT", "GIT_COMMIT"):
        value = os.environ.get(var, "")
        if value:
            return value[:9]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _system_health(console: Console) -> list[tuple[str, str, bool]]:
    """(label, value, ok) triples for the footer. Every check is a
    real check — nothing here is decorative."""
    kernel_ok = console.log.verify()
    event_count = sum(1 for _ in console.log.events())

    # Replay parity, the substrate's own correctness oracle, run live:
    # two independent rebuilds of Core entity state must agree exactly.
    replay_a, replay_b = EntityProjection(console.log), EntityProjection(console.log)
    replay_ok = ({k: vars(v) for k, v in replay_a.parties.items()} ==
                 {k: vars(v) for k, v in replay_b.parties.items()} and
                 {k: vars(v) for k, v in replay_a.missions.items()} ==
                 {k: vars(v) for k, v in replay_b.missions.items()})

    metric_ids = console.registry.owned_metric_ids()
    finance_count = sum(1 for m in metric_ids if m.startswith("finance."))
    tests = _test_count()

    kernel_value = (f"HASH CHAIN OK · {event_count} EVENTS" if kernel_ok
                    else "HASH CHAIN BROKEN")
    return [
        ("KERNEL", kernel_value, kernel_ok),
        ("CORE", f"{len(console.entities.parties)} PARTIES / "
                 f"{len(console.entities.missions)} MISSIONS", True),
        ("FINANCE", f"{finance_count} METRICS", finance_count > 0),
        ("METRICS", f"{len(metric_ids)} REGISTERED", len(metric_ids) > 0),
        ("VALIDATION", "REPLAY OK" if replay_ok else "REPLAY DIVERGED", replay_ok),
        ("TESTS", str(tests) if tests is not None else "NOT SHIPPED", tests is not None),
        ("VERSION", f"v{__version__}", True),
        ("COMMIT", _git_commit(), True),
    ]


# ------------------------------------------------------------------- layout

_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Foundry Mission Control</title>
<style>
  :root {{
    --bg: #0b0e12; --panel: #10141a; --line: #1d242d; --line-strong: #2b3440;
    --text: #e6edf3; --muted: #7d8894; --faint: #4d5661;
    --green: #3fb950; --amber: #d29922; --red: #f85149;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg); color: var(--text); min-height: 100vh; display: flex;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 15px; line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: inherit; text-decoration: none; }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .num  {{ font-variant-numeric: tabular-nums; }}

  nav {{
    width: 60px; border-right: 1px solid var(--line); padding: 20px 0;
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    position: sticky; top: 0; height: 100vh; flex-shrink: 0;
  }}
  nav .mark {{ color: var(--text); font-size: 15px; margin-bottom: 22px; }}
  nav a {{
    width: 38px; height: 38px; display: flex; align-items: center; justify-content: center;
    color: var(--faint); font-size: 12px; letter-spacing: .04em; border-radius: 6px;
    border: 1px solid transparent;
  }}
  nav a:hover {{ color: var(--muted); border-color: var(--line); }}
  nav a.active {{ color: var(--text); border-color: var(--line-strong); background: var(--panel); }}

  main {{ flex: 1; max-width: 1060px; padding: 44px 56px 72px; }}

  header.top {{
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 44px;
  }}
  h1.crumb {{ font-size: 11px; font-weight: 600; letter-spacing: .22em; color: var(--muted); }}
  .meta {{ font-size: 11px; letter-spacing: .06em; color: var(--faint); }}
  .meta a:hover {{ color: var(--muted); }}

  section {{ margin-bottom: 52px; }}
  h2 {{
    font-size: 11px; font-weight: 600; letter-spacing: .22em; color: var(--muted);
    border-bottom: 1px solid var(--line); padding-bottom: 10px; margin-bottom: 22px;
  }}

  .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%;
          margin-right: 12px; vertical-align: 2px; }}
  .dot.green {{ background: var(--green); box-shadow: 0 0 12px rgba(63,185,80,.5); }}
  .dot.amber {{ background: var(--amber); box-shadow: 0 0 12px rgba(210,153,34,.5); }}
  .dot.red   {{ background: var(--red);   box-shadow: 0 0 12px rgba(248,81,73,.5); }}
  .dot.none  {{ background: var(--faint); }}
  .status-word {{ font-size: 40px; font-weight: 650; letter-spacing: .04em; }}
  .status-word.green {{ color: var(--green); }}
  .status-word.amber {{ color: var(--amber); }}
  .status-word.red   {{ color: var(--red); }}
  .status-word.none  {{ color: var(--faint); }}
  .status-sub {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}

  .cards {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }}
  @media (max-width: 980px) {{ .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  .card {{
    border: 1px solid var(--line); border-radius: 8px; padding: 18px 18px 15px;
    background: var(--panel); display: block;
  }}
  a.card:hover {{ border-color: var(--line-strong); }}
  .card .label {{ font-size: 10px; letter-spacing: .18em; color: var(--muted); margin-bottom: 14px; }}
  .card .value {{ font-size: 26px; font-weight: 600; letter-spacing: -.01em; }}
  .card .value.na {{ color: var(--faint); font-weight: 400; }}
  .card .sub {{ font-size: 11px; color: var(--faint); margin-top: 8px; letter-spacing: .04em; }}
  .card .sub.warn {{ color: var(--amber); }}

  dl.brief {{ display: grid; grid-template-columns: max-content 1fr; gap: 12px 40px; }}
  dl.brief dt {{ font-size: 11px; letter-spacing: .18em; color: var(--muted); padding-top: 2px; }}
  dl.brief dd {{ font-size: 14px; }}
  dl.brief dd .dim {{ color: var(--muted); }}

  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th {{ text-align: left; font-size: 10px; letter-spacing: .18em; color: var(--muted);
        font-weight: 600; border-bottom: 1px solid var(--line); padding: 8px 18px 8px 0; }}
  td {{ border-bottom: 1px solid var(--line); padding: 9px 18px 9px 0; vertical-align: top; }}
  td.k {{ color: var(--muted); white-space: nowrap; }}

  pre {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
    padding: 16px; font-size: 12px; line-height: 1.6; overflow-x: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}

  footer {{
    border-top: 1px solid var(--line); padding-top: 18px; margin-top: 26px;
    display: flex; flex-wrap: wrap; gap: 8px 28px;
  }}
  footer .item {{ font-size: 10px; letter-spacing: .14em; color: var(--faint); }}
  footer .item b {{ color: var(--muted); font-weight: 600; margin-right: 7px; }}
  footer .item .ok {{ color: var(--green); }}
  footer .item .bad {{ color: var(--red); }}

  .empty {{ color: var(--muted); font-size: 14px; }}
  .placeholder {{ color: var(--faint); font-size: 14px; margin-top: 6px; }}
</style>
</head>
<body>
<nav>
  <div class="mark">◈</div>
  {nav_items}
</nav>
<main>
<header class="top">
  <h1 class="crumb">FOUNDRY · MISSION CONTROL</h1>
  <div class="meta">DATA AS OF {as_of} &nbsp;·&nbsp; <a href="/logout">SIGN OUT</a></div>
</header>
{body}
</main>
</body>
</html>
"""

_NAV = (("HO", "Home", "/"), ("FI", "Finance", "/finance"), ("DE", "Decisions", "/decisions"),
        ("MI", "Missions", "/missions"), ("SE", "Settings", "/settings"))


def _render(title: str, body: str, as_of: float, active_path: str) -> HTMLResponse:
    items = []
    for short, label, path in _NAV:
        active = ' class="active"' if path == active_path else ""
        items.append(f'<a href="{path}" title="{label}"{active}>{short}</a>')
    return HTMLResponse(_SHELL.format(
        title=html.escape(title), nav_items="\n  ".join(items),
        as_of=html.escape(_iso(as_of)), body=body))


def _footer(console: Console) -> str:
    items = []
    for label, value, ok in _system_health(console):
        klass = "ok" if ok else "bad"
        items.append(f'<div class="item"><b>{html.escape(label)}</b>'
                     f'<span class="{klass}">{html.escape(value)}</span></div>')
    return "<footer>" + "\n".join(items) + "</footer>"


# -------------------------------------------------------------------- pages

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if session_email(request) is None:
        return _login_redirect()
    console = _console(request)
    as_of = _as_of(console)
    scope = _household_scope(console)
    mission = _current_mission(console)

    # -- mission status banner: Core evaluates, this page only renders.
    rag = None
    mission_result = None
    if mission is not None and scope is not None:
        rag, mission_result = get_mission_status(
            mission.id, console.entities, console.registry, scope, as_of)
    if mission is None:
        banner_word, banner_class = "NO ACTIVE MISSION", "none"
    elif rag is None:
        # A Mission exists but its metric couldn't be evaluated —
        # honestly distinct from having no Mission at all.
        banner_word, banner_class = "NOT EVALUABLE", "none"
    else:
        banner_word, banner_class = _RAG_TO_BANNER.get(rag, (rag.upper(), "none"))
    banner_sub = (html.escape(mission.name) if mission is not None
                  else "Declare a Mission to give this console something to steer by.")

    # -- five KPI cards, each a Flight Deck tile (000 §14).
    cards_html = []
    tiles: dict[str, Tile] = {}
    if scope is not None:
        for label, metric_id, kind in KPI_CARDS:
            tile = compose_tile(metric_id, scope, console.registry,
                                console.entities, console.evidence, as_of)
            tiles[metric_id] = tile
            result = tile.current_value
            if result.status in ("available", "stale"):
                value_html = f'<div class="value num">{html.escape(_format_value(result.value, result.unit_or_currency, kind))}</div>'
                note = f"{len(result.limitations)} CAVEAT{'S' if len(result.limitations) != 1 else ''}" \
                    if result.limitations else result.status.upper()
                sub_class = "sub warn" if result.limitations else "sub"
            else:
                value_html = '<div class="value na">—</div>'
                note, sub_class = result.status.upper(), "sub"
            cards_html.append(
                f'<a class="card" href="/metrics/{html.escape(metric_id)}">'
                f'<div class="label">{html.escape(label)}</div>'
                f'{value_html}'
                f'<div class="{sub_class}">{html.escape(note)}</div></a>')
        cards = f'<div class="cards">{"".join(cards_html)}</div>'
    else:
        cards = ('<p class="empty">No household declared yet. Seed the event log '
                 '(see <span class="mono">examples/seed_mission_control.py</span>) '
                 'and reload — this console renders only real, replayed state.</p>')

    # -- mission brief.
    if mission is not None:
        target = "—"
        if mission.target_value is not None:
            kind = next((k for _, m, k in KPI_CARDS if m == mission.target_metric), "plain")
            unit = mission_result.unit_or_currency if mission_result else None
            target = (f"{mission.target_metric} ≥ "
                      f"{_format_value(mission.target_value, unit, kind)}")
            if mission.tolerance:
                target += f" (±{_format_value(mission.tolerance, unit, kind)})"
        next_decision = "—"
        any_tile = next(iter(tiles.values()), None)
        if any_tile is not None and any_tile.next_decision:
            claims = [console.canon.claims.get(cid) for cid in any_tile.next_decision]
            claims = [c for c in claims if c is not None and c.status == "active"]
            if claims:
                latest = max(claims, key=lambda c: c.ts)
                next_decision = html.escape(latest.statement)
        brief = f"""<dl class="brief">
  <dt>CURRENT MISSION</dt><dd>{html.escape(mission.name)}</dd>
  <dt>MISSION STATUS</dt><dd><span class="dot {banner_class}"></span>{html.escape(banner_word if rag else "NOT EVALUABLE")}</dd>
  <dt>CURRENT TARGET</dt><dd class="num">{html.escape(target)}</dd>
  <dt>NEXT DECISION</dt><dd>{next_decision}</dd>
</dl>"""
    else:
        brief = '<p class="empty">No active Mission.</p>'

    body = f"""<section>
  <h2>MISSION STATUS</h2>
  <div><span class="dot {banner_class}"></span><span class="status-word {banner_class}">{html.escape(banner_word)}</span></div>
  <div class="status-sub">{banner_sub}</div>
</section>
<section>
  <h2>KEY INDICATORS</h2>
  {cards}
</section>
<section>
  <h2>MISSION BRIEF</h2>
  {brief}
</section>
{_footer(console)}"""
    return _render("Home", body, as_of, "/")


@router.get("/metrics/{metric_id}", response_class=HTMLResponse)
def metric_drill_down(request: Request, metric_id: str):
    """Drill-down: the full MetricResult contract (000 §13.3), plus a
    per-member attribution table — JSON and simple tables only, per
    RFC-003. An unknown metric_id renders as UNSUPPORTED, exactly what
    the registry returns; the page cannot crash on a bad id."""
    if session_email(request) is None:
        return _login_redirect()
    console = _console(request)
    as_of = _as_of(console)
    scope = _household_scope(console)
    if scope is None:
        return _render("Metric", '<p class="empty">No household declared yet.</p>' + _footer(console),
                       as_of, "/")

    label, kind = next(((l, k) for l, m, k in KPI_CARDS if m == metric_id),
                       (metric_id.upper(), "plain"))
    result = console.registry.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))

    headline = (_format_value(result.value, result.unit_or_currency, kind)
                if result.status in ("available", "stale") else result.status.upper())

    # Per-member attribution — the same metric, dispatched per person
    # through the identical registry path. Composition, not calculation.
    rows = [f'<tr><td class="k">HOUSEHOLD</td><td class="mono">{html.escape(scope.id[:8])}</td>'
            f'<td class="num">{html.escape(_format_value(result.value, result.unit_or_currency, kind))}</td>'
            f'<td>{html.escape(result.status.upper())}</td></tr>']
    for member in console.entities.members_of(scope.id):
        member_result = console.registry.dispatch(MetricRequest(
            metric_id=metric_id, scope=Subject("party", member.id), as_of=as_of))
        rows.append(
            f'<tr><td class="k">MEMBER</td><td class="mono">{html.escape(member.id[:8])}</td>'
            f'<td class="num">{html.escape(_format_value(member_result.value, member_result.unit_or_currency, kind))}</td>'
            f'<td>{html.escape(member_result.status.upper())}</td></tr>')

    limitations = ("".join(f"<li>{html.escape(l)}</li>" for l in result.limitations)
                   or "<li>none</li>")

    raw = {
        "metric_id": result.metric_id, "value": result.value,
        "unit_or_currency": result.unit_or_currency,
        "scope": {"kind": result.scope.kind, "id": result.scope.id},
        "as_of": result.as_of, "status": result.status,
        "calculation_version": result.calculation_version,
        "input_references": list(result.input_references),
        "evidence_references": list(result.evidence_references),
        "assumption_references": list(result.assumption_references),
        "confidence_or_quality": result.confidence_or_quality,
        "limitations": list(result.limitations),
    }

    body = f"""<section>
  <h2>{html.escape(label)} · <span class="mono">{html.escape(metric_id)}</span></h2>
  <div class="status-word num" style="color: var(--text);">{html.escape(headline)}</div>
  <div class="status-sub">status {html.escape(result.status.upper())} · calculation
  <span class="mono">{html.escape(result.calculation_version or "—")}</span> ·
  {len(result.input_references)} input event(s) · quality
  {html.escape(str(result.confidence_or_quality or "—"))}</div>
</section>
<section>
  <h2>ATTRIBUTION</h2>
  <table>
    <tr><th>SCOPE</th><th>PARTY</th><th>VALUE</th><th>STATUS</th></tr>
    {"".join(rows)}
  </table>
</section>
<section>
  <h2>CAVEATS</h2>
  <ul style="list-style: none; font-size: 13px; color: var(--muted); line-height: 2;">{limitations}</ul>
</section>
<section>
  <h2>RAW RESULT</h2>
  <pre>{html.escape(json.dumps(raw, indent=2))}</pre>
</section>
{_footer(console)}"""
    return _render(label.title(), body, as_of, "/")


def _placeholder(request: Request, path: str, title: str, note: str):
    if session_email(request) is None:
        return _login_redirect()
    console = _console(request)
    body = f"""<section>
  <h2>{html.escape(title.upper())}</h2>
  <p class="empty">Not yet implemented.</p>
  <p class="placeholder">{html.escape(note)}</p>
</section>
{_footer(console)}"""
    return _render(title, body, _as_of(console), path)


@router.get("/finance", response_class=HTMLResponse)
def finance_page(request: Request):
    return _placeholder(request, "/finance", "Finance",
                        "Account, asset, and position drill-down surfaces arrive "
                        "after the projection engine (RFC-004).")


@router.get("/decisions", response_class=HTMLResponse)
def decisions_page(request: Request):
    return _placeholder(request, "/decisions", "Decisions",
                        "The Decision → Execution → Outcome → Review loop "
                        "(000 §12) gets its surface once decisions flow through it.")


@router.get("/missions", response_class=HTMLResponse)
def missions_page(request: Request):
    return _placeholder(request, "/missions", "Missions",
                        "Mission declaration and target management. The home page "
                        "evaluates the current Mission read-only until then.")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return _placeholder(request, "/settings", "Settings",
                        "Household selection, reporting currency, and data-source "
                        "configuration.")
