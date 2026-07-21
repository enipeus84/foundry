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

Design (RFC-003, restyled by RFC-004): calm, sparse, high-signal,
dark-first, typography over chrome. Server-rendered HTML, one small
local script for accessible drawer behaviour, and zero new dependencies.
RFC-004.2's Flight Deck language — a full-bleed photographic Earthrise,
NOMINAL / WATCH / OFF COURSE, the four-lane Apollo programme, the Flight
Director, and Recent Course Corrections — is presentation only: every number still arrives
through the Metric Registry and the Flight Deck tile contract, every
insight through the Evidence Index, and the page stays deterministic
for a given log (the sunrise phase derives from `as_of`, never the
wall clock).
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


# The four opening-screen KPIs (RFC-004: exactly four). Metric
# identifiers are the registry's public contract (000 §13.1) — strings,
# not imports. Every other metric remains one click deeper at
# /metrics/{id}. The fourth element is a measurement-period qualifier
# (RFC-004B, Information Honesty): finance.cash_flow with no horizon
# is net flow over every observed transaction, and the card must say
# so rather than let the reader assume a monthly figure.
KPI_CARDS: tuple[tuple[str, str, str, str], ...] = (
    ("NET WORTH", "finance.net_worth", "currency", ""),
    ("LIQUIDITY", "finance.cash_available", "currency", ""),
    ("CASH FLOW", "finance.cash_flow", "currency", "SINCE FIRST OBSERVATION"),
    ("RUNWAY", "finance.liquidity_runway", "months", ""),
)

# Presentation-only Mission programme. These lanes create no Mission entities
# and carry no financial values unless an existing active Mission can be shown
# inside them. Empty lanes are visibly labelled PLANNED / TARGET NOT DECLARED.
_MISSION_LANES: tuple[tuple[str, str, str], ...] = (
    ("mortgage", "Mortgage Freedom", "Own the home outright."),
    ("independence", "Financial Independence", "Build lasting freedom of choice."),
    ("retirement", "Retirement", "Fund the life beyond work."),
    ("children", "Children's Future", "Create long-term optionality."),
)

# Drill-down pages for metrics no longer on the opening screen keep
# their labels and formats here.
_METRIC_PRESENTATION: dict[str, tuple[str, str]] = {
    "finance.net_worth": ("NET WORTH", "currency"),
    "finance.cash_available": ("LIQUIDITY", "currency"),
    "finance.cash_flow": ("NET CASH FLOW", "currency"),
    "finance.liquidity_runway": ("RUNWAY", "months"),
    "finance.employer_concentration": ("EMPLOYER CONCENTRATION", "percent"),
    "finance.debt_ratio": ("DEBT RATIO", "percent"),
}

# NASA flight-status vocabulary (Design Constitution): Core's RAG
# evaluation rendered as flight language, never recomputed here.
_RAG_TO_BANNER = {
    "on_track": ("NOMINAL", "green"),
    "achieved": ("NOMINAL", "green"),
    "at_risk": ("WATCH", "amber"),
    "off_track": ("OFF COURSE", "red"),
}

# Worst-status-wins ordering for aggregating several active Missions
# into the single FLIGHT PLAN word.
_RAG_SEVERITY = {"off_track": 0, "at_risk": 1, "on_track": 2, "achieved": 3}

_VERDICT_GLYPH = {
    "achieved": ("✓", "green"),
    "partially_achieved": ("✓", "amber"),
    "not_achieved": ("✕", "red"),
    "inconclusive": ("·", "none"),
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


def _active_missions(console: Console) -> list[Mission]:
    """Every active Mission, in declaration order. Aggregation into the
    single FLIGHT PLAN word is worst-status-wins, done at render time
    from Core's evaluations."""
    return [m for m in console.entities.missions.values() if m.status == "active"]


def _mission_lane(name: str) -> str | None:
    """Choose a visual programme lane from an existing Mission name.

    This is display taxonomy only: it never creates or evaluates a Mission,
    and the real Mission name remains visible. Unknown names remain visible
    as additional live rows rather than being forced into a false category.
    """
    text = name.casefold()
    if "mortgage" in text or "home" in text:
        return "mortgage"
    if "child" in text or "education" in text:
        return "children"
    if "retire" in text or "pension" in text:
        return "retirement"
    if "independ" in text or "fire" in text:
        return "independence"
    return None


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


def _short_date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else "—"


def _sun_phase(as_of: float) -> str:
    """The Earthrise hero's sunrise progression (Design Constitution).
    Derived from `as_of` — the data's own clock — never the wall clock,
    so two renders of the same log stay byte-identical."""
    hour = time.gmtime(as_of).tm_hour
    if 5 <= hour < 9:
        return "dawn"
    if 9 <= hour < 17:
        return "day"
    if 17 <= hour < 21:
        return "dusk"
    return "night"


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
<link rel="preload" as="image" href="/static/earthrise.webp" type="image/webp" fetchpriority="high">
<style>
  :root {{
    --bg: #05080c; --surface: #090e14; --panel: #0d131b; --elevated: #111923;
    --line: #202a35; --line-strong: #344252;
    --text: #edf2f7; --muted: #9aa8b6; --faint: #6f7c89;
    --green: #66c56f; --amber: #e0a83c; --red: #ed6a64; --blue: #64a5e8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  [hidden] {{ display: none !important; }}
  body {{
    background: var(--bg); color: var(--text); min-height: 100vh;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 15px; line-height: 1.5; overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
  }}
  body.nav-open {{ overflow: hidden; }}
  a {{ color: inherit; text-decoration: none; }}
  button {{ font: inherit; }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .num  {{ font-variant-numeric: tabular-nums; }}
  .sr-only {{
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
  }}
  :focus-visible {{ outline: 2px solid var(--text); outline-offset: 3px; }}

  .skip {{
    position: absolute; left: -9999px; top: 8px; z-index: 90; padding: 8px 14px;
    background: var(--panel); border: 1px solid var(--line-strong); border-radius: 6px;
    font-size: 12px; letter-spacing: .08em;
  }}
  .skip:focus {{ left: 8px; }}

  /* Deliberate-click navigation; no hover-only state. */
  .menu-btn {{
    position: fixed; top: 18px; left: 20px; z-index: 60; cursor: pointer;
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 10px; border: 1px solid var(--line); border-radius: 4px;
    background: rgba(9,14,20,.94); color: var(--muted);
    font-size: 10px; font-weight: 650; letter-spacing: .2em;
  }}
  .menu-btn:hover {{ color: var(--text); border-color: var(--line-strong); }}
  .drawer-shell {{ position: fixed; inset: 0; z-index: 70; }}
  .drawer-backdrop {{
    position: absolute; inset: 0; width: 100%; border: 0; cursor: default;
    background: rgba(1,4,8,.7); backdrop-filter: blur(3px);
  }}
  .drawer {{
    position: absolute; inset: 0 auto 0 0; width: min(310px, 88vw);
    background: #080d13; border-right: 1px solid var(--line-strong);
    padding: 24px 18px; display: flex; flex-direction: column; gap: 3px;
    animation: drawer-in .18s ease-out both;
  }}
  @keyframes drawer-in {{ from {{ transform: translateX(-100%); }} to {{ transform: none; }} }}
  .drawer-head {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 34px; padding: 0 8px;
  }}
  .drawer .mark {{ font-size: 12px; font-weight: 650; letter-spacing: .22em; color: var(--text); }}
  .drawer-close {{
    width: 38px; height: 38px; border: 1px solid var(--line); background: transparent;
    color: var(--muted); cursor: pointer; font-size: 20px;
  }}
  .drawer a {{
    padding: 13px 12px; color: var(--muted);
    font-size: 11px; font-weight: 650; letter-spacing: .18em;
    border-left: 2px solid transparent;
  }}
  .drawer a:hover {{ color: var(--text); background: var(--surface); }}
  .drawer a.active {{ color: var(--text); background: var(--surface); border-left-color: var(--green); }}
  .drawer a.sign-out {{ margin-top: auto; border-top: 1px solid var(--line); }}
  .noscript-nav {{
    position: relative; z-index: 5; max-width: 1256px; margin: 76px auto 0;
    padding: 12px 16px; border-block: 1px solid var(--line);
    color: var(--muted); font-size: 10px; letter-spacing: .1em;
  }}
  .noscript-nav nav {{ display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 8px; }}
  .noscript-nav a {{ color: var(--text); text-decoration: underline; text-underline-offset: 3px; }}
  @media (prefers-reduced-motion: reduce) {{
    .drawer {{ animation: none; }}
    .card.kpi, .card.mission, .card .drill {{ transition: none; }}
  }}

  header.top {{
    position: absolute; inset: 0 0 auto; z-index: 4; width: 100%;
    display: flex; justify-content: space-between; align-items: center; gap: 16px;
    max-width: 1320px; margin: 0 auto; padding: 24px 32px 0 112px; min-height: 66px;
  }}
  h1.crumb {{ font-size: 10px; font-weight: 650; letter-spacing: .26em; color: var(--muted); }}
  .meta {{ font-size: 10px; letter-spacing: .12em; color: var(--faint); text-align: right; }}
  .meta a {{ margin-left: 8px; }}
  .meta a:hover {{ color: var(--muted); }}

  main {{ max-width: 1320px; margin: 0 auto; padding: 0 32px 72px; }}
  @media (max-width: 820px) {{
    header.top {{ padding-left: 116px; justify-content: flex-end; }}
    /* The brand crumb stays for screen readers; visually the MENU
       control and drawer carry the identity on small screens. */
    h1.crumb {{
      position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip-path: inset(50%); white-space: nowrap;
    }}
    .meta {{ font-size: 9px; }}
  }}

  section {{ margin-bottom: 74px; }}
  h2 {{
    font-size: 10px; font-weight: 650; letter-spacing: .26em; color: var(--muted);
    border: 0; padding: 0; margin-bottom: 24px;
  }}

  /* -------------------------------------------------- Earthrise hero. */
  .hero {{
    position: relative; width: 100vw; min-height: 620px;
    margin-left: calc(50% - 50vw); margin-bottom: 78px;
    border: 0; border-bottom: 1px solid var(--line); border-radius: 0;
    overflow: hidden; background: #020407;
  }}
  .hero img.earthrise {{
    position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
    object-position: 54% 58%;
  }}
  .hero .scrim {{
    position: absolute; inset: 0;
    background:
      linear-gradient(90deg, rgba(1,4,8,.88) 0%, rgba(1,4,8,.58) 34%, rgba(1,4,8,.12) 68%, rgba(1,4,8,.04) 100%),
      linear-gradient(0deg, rgba(1,4,8,.34) 0%, transparent 38%);
  }}
  .hero-content {{
    position: relative; z-index: 1; width: min(100%, 1320px); min-height: 620px;
    margin: 0 auto; padding: 118px 72px 64px;
    display: flex; flex-direction: column; justify-content: flex-end;
  }}
  .hero-content > * {{ max-width: 680px; }}
  .eyebrow {{ font-size: 10px; font-weight: 650; letter-spacing: .28em; color: #aab6c2; }}
  .flight-word {{
    border: 0; padding: 0; font-size: clamp(58px, 7vw, 92px); font-weight: 540;
    letter-spacing: .075em; line-height: .96; margin: 10px 0 20px;
  }}
  .flight-word.green {{ color: var(--green); }}
  .flight-word.amber {{ color: var(--amber); }}
  .flight-word.red   {{ color: var(--red); }}
  .flight-word.none  {{ color: var(--muted); }}
  .hero .why {{ color: #d2d9e1; font-size: 17px; line-height: 1.55; max-width: 54ch; }}
  .hero-stats {{ display: flex; flex-wrap: wrap; gap: 16px 56px; margin-top: 36px; }}
  .hero-stats .stat .k {{ font-size: 9px; font-weight: 650; letter-spacing: .22em; color: #8d9aa7; }}
  .hero-stats .stat .v {{ font-size: 16px; font-weight: 650; letter-spacing: .08em; margin-top: 4px; }}
  .hero-stats .v.green {{ color: var(--green); }}
  .hero-stats .v.amber {{ color: var(--amber); }}
  .phase-dawn img.earthrise {{ filter: saturate(.96) sepia(.05); }}
  .phase-day img.earthrise {{ filter: brightness(1.02); }}
  .phase-dusk img.earthrise {{ filter: saturate(.9) hue-rotate(-4deg); }}

  /* ------------------------------------------------ primary telemetry. */
  .cards {{
    display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: clamp(28px, 4vw, 64px); border-top: 1px solid var(--line);
    padding-top: 30px;
  }}
  .card {{ display: block; min-width: 0; }}
  .card.kpi {{
    position: relative; padding: 0 0 18px; transition: transform .16s ease-out;
  }}
  a.card.kpi:hover {{ transform: translateY(-2px); }}
  .card .label {{
    display: flex; gap: 10px; align-items: baseline;
    font-size: 9px; font-weight: 650; letter-spacing: .21em; color: var(--muted);
  }}
  .card .channel {{ color: var(--green); font-variant-numeric: tabular-nums; }}
  .card .value {{
    font-size: clamp(30px, 3vw, 42px); font-weight: 530; letter-spacing: -.025em;
    margin-top: 18px;
  }}
  .card .value.na {{ color: var(--faint); font-weight: 400; }}
  .card .sub {{ font-size: 9px; color: var(--faint); margin-top: 10px; letter-spacing: .1em; }}
  .card .sub.warn {{ color: var(--amber); }}
  .card .drill {{
    position: absolute; top: -4px; right: 0; font-size: 15px;
    color: var(--faint); transition: color .16s ease-out, transform .16s ease-out;
  }}
  a.card.kpi:hover .drill {{ color: var(--text); transform: translate(2px,-2px); }}

  /* ---------------------------------------------- Apollo mission rows. */
  .missions {{ border-top: 1px solid var(--line); }}
  .card.mission {{
    display: grid; grid-template-columns: 54px minmax(230px,.88fr) minmax(360px,1.55fr) 126px 24px;
    align-items: center; gap: 26px; padding: 28px 2px; border-bottom: 1px solid var(--line);
  }}
  .m-number {{ font-size: 12px; letter-spacing: .14em; color: var(--faint); }}
  .m-name {{ font-size: 18px; font-weight: 550; margin-bottom: 5px; }}
  .m-purpose {{ font-size: 11px; color: var(--faint); line-height: 1.5; }}
  .m-progress {{ font-size: 9px; color: var(--muted); letter-spacing: .09em; }}
  .m-status {{ justify-self: end; font-size: 10px; font-weight: 700; letter-spacing: .18em; white-space: nowrap; }}
  .m-status.green {{ color: var(--green); }}
  .m-status.amber {{ color: var(--amber); }}
  .m-status.red   {{ color: var(--red); }}
  .m-status.none  {{ color: var(--faint); }}
  .m-gauge {{ position: relative; height: 20px; margin-top: 13px; }}
  .m-gauge::before {{
    content: ""; position: absolute; left: 0; right: 0; top: 8px; height: 4px;
    background: var(--line);
  }}
  .m-gauge .zone {{
    position: absolute; left: 33.33%; right: 33.33%; top: 5px; height: 10px;
    background: #344356;
  }}
  .m-gauge .tick {{
    position: absolute; top: 0; width: 3px; height: 20px; margin-left: -1px;
    background: var(--muted); box-shadow: 0 0 0 3px rgba(5,8,12,.75);
  }}
  .m-gauge .tick.green {{ background: var(--green); }}
  .m-gauge .tick.amber {{ background: var(--amber); }}
  .m-gauge .tick.red   {{ background: var(--red); }}
  .m-link {{ justify-self: end; font-size: 19px; color: var(--faint); }}
  .m-link.unavailable {{ font-size: 12px; letter-spacing: .08em; }}
  a.card.mission {{ transition: transform .16s ease-out; }}
  a.card.mission:hover {{ transform: translateX(3px); }}
  a.card.mission:hover .m-link {{ color: var(--text); }}
  .card.mission.planned {{ color: var(--muted); }}
  .card.mission.planned .m-purpose {{ color: var(--faint); }}
  .card.mission.planned .m-status {{ color: var(--faint); }}
  .m-gauge.planned::before {{
    background: repeating-linear-gradient(90deg, var(--line) 0 12px, transparent 12px 19px);
  }}

  /* --------------------- Flight Director & Recent Course Corrections. */
  .duo {{ display: block; }}
  .duo section {{ margin-bottom: 74px; }}
  .flight-director .director-copy {{
    max-width: 880px; border-left: 2px solid var(--green); padding: 3px 0 4px 28px;
  }}
  .panel {{ padding: 0; }}
  .fd-lede {{ font-size: 14px; color: var(--muted); margin: 9px 0 0; }}
  .fd-statement {{ font-size: 17px; line-height: 1.6; max-width: 66ch; margin-top: 22px; }}
  .fd-meta {{ font-size: 9px; font-weight: 650; letter-spacing: .16em; color: var(--faint); margin-top: 16px; }}
  .fd-nominal {{ font-size: clamp(23px, 2.4vw, 32px); font-weight: 520; line-height: 1.25; }}
  .fd-sub {{ font-size: 14px; color: var(--muted); margin-top: 10px; }}
  ul.corrections {{ list-style: none; }}
  ul.corrections li {{
    display: grid; grid-template-columns: 24px 1fr; gap: 14px;
    padding: 21px 0; border-top: 1px solid var(--line);
  }}
  .tick {{ width: 20px; text-align: center; font-weight: 700; }}
  .tick.green {{ color: var(--green); }}
  .tick.amber {{ color: var(--amber); }}
  .tick.red   {{ color: var(--red); }}
  .tick.none  {{ color: var(--faint); }}
  .corrections p {{ font-size: 14px; line-height: 1.6; max-width: 78ch; }}
  .corrections .c-meta {{ font-size: 9px; font-weight: 650; letter-spacing: .16em; color: var(--faint); margin-top: 6px; }}

  /* ----------------------------------------------- honest scope strip. */
  .scope-bar {{
    margin-top: 10px; border-top: 1px solid var(--line); padding-top: 25px;
    display: flex; align-items: center; gap: clamp(18px, 4vw, 48px); flex-wrap: wrap;
  }}
  .scope-label {{ margin-right: 8px; font-size: 9px; letter-spacing: .22em; color: var(--faint); }}
  .scope-bar button {{
    position: relative; border: 0; padding: 0; color: var(--faint);
    background: transparent; font-size: 11px; letter-spacing: .08em;
  }}
  .scope-bar button.active {{ color: var(--text); padding-left: 15px; }}
  .scope-bar button.active::before {{
    content: ""; position: absolute; left: 0; top: .46em; width: 6px; height: 6px;
    border-radius: 50%; background: var(--green);
  }}
  .scope-bar button[disabled] {{ cursor: not-allowed; opacity: .82; }}
  .scope-bar small {{ display: block; margin-top: 3px; font-size: 7px; letter-spacing: .14em; color: var(--faint); }}

  /* -------------------------------------------- drill-down page bits. */
  .status-word {{ font-size: 40px; font-weight: 650; letter-spacing: .04em; }}
  .status-word.green {{ color: var(--green); }}
  .status-word.amber {{ color: var(--amber); }}
  .status-word.red   {{ color: var(--red); }}
  .status-word.none  {{ color: var(--faint); }}
  .status-sub {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}

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
    border-top: 1px solid var(--line); padding-top: 18px; margin-top: 46px;
    display: flex; flex-wrap: wrap; gap: 8px 28px;
  }}
  footer .item {{ font-size: 10px; letter-spacing: .14em; color: var(--faint); }}
  footer .item b {{ color: var(--muted); font-weight: 600; margin-right: 7px; }}
  footer .item .ok {{ color: var(--green); }}
  footer .item .bad {{ color: var(--red); }}

  .empty {{ color: var(--muted); font-size: 14px; }}
  .placeholder {{ color: var(--faint); font-size: 14px; margin-top: 6px; }}

  @media (max-width: 980px) {{
    .cards {{ grid-template-columns: repeat(2, minmax(0,1fr)); gap: 48px 40px; }}
    .card.mission {{ grid-template-columns: 42px minmax(0,1fr) auto; gap: 14px 18px; }}
    .m-telemetry {{ grid-column: 2 / -1; }}
    .m-link {{ grid-column: 3; grid-row: 1; }}
    .m-status {{ grid-column: 3; grid-row: 2; }}
  }}
  @media (max-width: 620px) {{
    .menu-btn {{ top: 14px; left: 14px; }}
    header.top {{ min-height: 56px; padding: 18px 16px 0 94px; }}
    .meta .timestamp {{ display: none; }}
    .meta a {{ color: var(--muted); }}
    main {{ padding: 0 16px 48px; }}
    section {{ margin-bottom: 58px; }}
    h2 {{ margin-bottom: 20px; }}
    .hero {{ min-height: 560px; margin-bottom: 62px; }}
    .hero img.earthrise {{ object-position: 67% 54%; }}
    .hero .scrim {{ background: linear-gradient(180deg, rgba(1,4,8,.08) 0%, rgba(1,4,8,.28) 38%, rgba(1,4,8,.94) 78%, rgba(1,4,8,.98) 100%); }}
    .hero-content {{ min-height: 560px; padding: 104px 24px 38px; max-width: none; }}
    .flight-word {{ font-size: clamp(45px, 14vw, 58px); letter-spacing: .055em; }}
    .hero .why {{ font-size: 15px; }}
    .hero-stats {{ gap: 16px 28px; margin-top: 24px; }}
    .hero-stats .stat {{ min-width: 112px; }}
    .cards {{ gap: 38px 22px; padding-top: 24px; }}
    .card.kpi {{ padding: 0; }}
    .card .label {{ gap: 7px; letter-spacing: .15em; }}
    .card .value {{ font-size: clamp(24px, 7.2vw, 31px); margin-top: 14px; }}
    .card .sub {{ min-height: 1.4em; line-height: 1.4; }}
    .card.mission {{ grid-template-columns: 34px minmax(0,1fr); gap: 11px 14px; padding: 22px 4px; }}
    .m-number {{ grid-row: 1 / span 2; align-self: start; padding-top: 3px; }}
    .m-identity {{ grid-column: 2; grid-row: 1; padding-right: 28px; }}
    .m-status {{ grid-column: 2; grid-row: 2; justify-self: start; }}
    .m-telemetry {{ grid-column: 1 / -1; grid-row: 3; }}
    .m-link {{ grid-column: 2; grid-row: 1; }}
    .flight-director .director-copy {{ padding-left: 20px; }}
    .scope-bar {{ gap: 22px 18px; }}
    .scope-label {{ flex-basis: 100%; margin: 0; }}
    .scope-bar button {{ flex: 1 1 calc(50% - 18px); text-align: left; }}
    .scope-bar button:last-child {{ flex-basis: 100%; }}
  }}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<button class="menu-btn" id="nav-open" type="button" aria-controls="primary-drawer" aria-expanded="false">
  <span aria-hidden="true">☰</span>MENU
</button>
<noscript>
  <style>#nav-open {{ display: none; }}</style>
  <div class="noscript-nav">
    <p>JavaScript is unavailable. The navigation drawer cannot open; use these direct links.</p>
    <nav aria-label="Primary navigation (JavaScript unavailable)">
      {nav_items}
      <a href="/logout">SIGN OUT</a>
    </nav>
  </div>
</noscript>
<div class="drawer-shell" id="primary-drawer" role="dialog" aria-modal="true" aria-label="Navigation" hidden>
  <button class="drawer-backdrop" type="button" tabindex="-1" data-nav-dismiss aria-label="Close navigation"></button>
  <nav class="drawer" aria-label="Primary">
    <div class="drawer-head"><div class="mark">◈ FOUNDRY</div>
      <button class="drawer-close" type="button" data-nav-close aria-label="Close navigation">×</button>
    </div>
    {nav_items}
    <a class="sign-out" href="/logout">SIGN OUT</a>
  </nav>
</div>
<header class="top">
  <h1 class="crumb">FOUNDRY · MISSION CONTROL</h1>
  <div class="meta"><span class="timestamp">DATA AS OF {as_of} &nbsp;·&nbsp;</span><a href="/logout">SIGN OUT</a></div>
</header>
<main id="main">
{body}
</main>
<script src="/static/flight-deck.js" defer></script>
</body>
</html>
"""

_NAV = (("FLIGHT DECK", "/"), ("FINANCE", "/finance"), ("DECISIONS", "/decisions"),
        ("MISSIONS", "/missions"), ("SETTINGS", "/settings"))

_EARTHRISE_PATH = "/static/earthrise.webp"


def _render(title: str, body: str, as_of: float, active_path: str) -> HTMLResponse:
    items = []
    for label, path in _NAV:
        active = ' class="active" aria-current="page"' if path == active_path else ""
        items.append(f'<a href="{path}"{active}>{label}</a>')
    return HTMLResponse(_SHELL.format(
        title=html.escape(title), nav_items="\n    ".join(items),
        as_of=html.escape(_iso(as_of)), body=body))


def _footer(console: Console) -> str:
    items = []
    for label, value, ok in _system_health(console):
        klass = "ok" if ok else "bad"
        items.append(f'<div class="item"><b>{html.escape(label)}</b>'
                     f'<span class="{klass}">{html.escape(value)}</span></div>')
    return "<footer>" + "\n".join(items) + "</footer>"


# -------------------------------------------------------------------- pages

def _active_claims(console: Console, claim_ids) -> list:
    """Resolve claim ids to active Canon claims, deterministically
    ordered (newest first, id as tiebreaker)."""
    claims = [console.canon.claims.get(cid) for cid in sorted(claim_ids)]
    claims = [c for c in claims if c is not None and c.status == "active"]
    claims.sort(key=lambda c: (-c.ts, c.id))
    return claims


# ------------------------------------------- mission deviation (RFC-004B)
#
# Core's Mission policy (mission_evaluation.py) is *proximity*: distance
# from the declared target (or range edge) measured against tolerance.
# A fill-toward-100% bar assumes "higher is better" and misrepresents
# lower-is-better Missions, so the card renders a deviation gauge
# instead: a track spanning ±3 tolerances and a tick at the current
# deviation. Target-value Missions also shade their ±1 tolerance band,
# which is exactly Core's on-track policy. Range Missions deliberately
# omit that band: Core considers any value outside the range WATCH even
# when it is within one tolerance of the edge, so a central shaded band
# would make the picture disagree with the policy. Missions without a
# numeric target or tolerance get no gauge — never an invented one.

def _mission_deviation(mission: Mission, result) -> tuple[float | None, bool]:
    """Signed distance from the Mission's declared target, in the
    metric's own units — 0.0 when inside a declared range. (deviation,
    is_range); deviation is None when no honest comparison exists."""
    if result is None or result.status not in ("available", "stale") \
            or result.value is None:
        return None, False
    value = result.value
    if mission.target_range is not None:
        lo, hi = mission.target_range
        if value < lo:
            return value - lo, True
        if value > hi:
            return value - hi, True
        return 0.0, True
    if mission.target_value is not None:
        return value - mission.target_value, False
    return None, False


def _variance_text(deviation: float | None, is_range: bool,
                   unit: str | None, kind: str) -> str:
    """The signed variance, spelled out — the number the gauge draws,
    stated in text so the visual never carries meaning the words
    don't."""
    if deviation is None:
        return ""
    if deviation == 0.0:
        return "WITHIN RANGE" if is_range else "ON TARGET"
    sign = "+" if deviation > 0 else "−"
    noun = "OUTSIDE RANGE" if is_range else "FROM TARGET"
    return f"{sign}{_format_value(abs(deviation), unit, kind)} {noun}"


def _deviation_gauge(deviation: float, tolerance: float, klass: str,
                     is_range: bool = False) -> str:
    """Tick position: deviation in tolerance units, clamped to ±3 and
    mapped onto the track. Only target-value Missions get a shaded
    tolerance band; range status semantics do not support one."""
    units = max(-3.0, min(3.0, deviation / tolerance))
    left = 50.0 + units / 6.0 * 100.0
    zone = '' if is_range else '<span class="zone"></span>'
    return (f'<div class="m-gauge" aria-hidden="true">{zone}'
            f'<span class="tick {klass}" style="left:{left:.1f}%"></span></div>')


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if session_email(request) is None:
        return _login_redirect()
    console = _console(request)
    as_of = _as_of(console)
    scope = _household_scope(console)
    missions = _active_missions(console)

    # -- Core evaluates every active Mission; this page only renders.
    evaluated = []  # (mission, rag, result)
    if scope is not None:
        for mission in missions:
            rag, result = get_mission_status(
                mission.id, console.entities, console.registry, scope, as_of)
            evaluated.append((mission, rag, result))

    # -- FLIGHT PLAN: worst status wins across active Missions. When
    #    the worst status is a deviation, remember which Mission caused
    #    it — the Flight Director must speak to that Mission (RFC-004B).
    rags = [rag for _, rag, _ in evaluated if rag is not None]
    deviating: Mission | None = None
    if not missions:
        banner_word, banner_class = "NO ACTIVE MISSION", "none"
    elif not rags:
        # Missions exist but none could be evaluated — honestly
        # distinct from having no Mission at all.
        banner_word, banner_class = "NOT EVALUABLE", "none"
    else:
        worst = min(rags, key=lambda r: _RAG_SEVERITY.get(r, 0))
        banner_word, banner_class = _RAG_TO_BANNER.get(worst, (worst.upper(), "none"))
        if worst in ("at_risk", "off_track"):
            deviating = next((m for m, rag, _ in evaluated if rag == worst), None)

    # -- four KPI cards, each a Flight Deck tile (000 §14).
    cards_html = []
    tiles: dict[str, Tile] = {}
    if scope is not None:
        for channel, (label, metric_id, kind, period) in enumerate(KPI_CARDS, start=1):
            tile = compose_tile(metric_id, scope, console.registry,
                                console.entities, console.evidence, as_of)
            tiles[metric_id] = tile
            result = tile.current_value
            if result.status in ("available", "stale"):
                value_html = f'<div class="value num">{html.escape(_format_value(result.value, result.unit_or_currency, kind))}</div>'
                note = (f"{len(result.limitations)} CAVEAT"
                        f"{'S' if len(result.limitations) != 1 else ''}"
                        if result.limitations else "")
                sub_class = "sub warn" if result.limitations else "sub"
            else:
                value_html = '<div class="value na">—</div>'
                note, sub_class = result.status.upper(), "sub"
            if period:
                note = f"{note} · {period}" if note else period
            note_html = (f'<div class="{sub_class}">{html.escape(note)}</div>'
                         if note else "")
            cards_html.append(
                f'<a class="card kpi" href="/metrics/{html.escape(metric_id)}">'
                f'<div class="label"><span class="channel">{channel:02d}</span>'
                f'<span>{html.escape(label)}</span></div>'
                f'{value_html}'
                f'{note_html}'
                f'<span class="drill" aria-hidden="true">↗</span>'
                f'<span class="sr-only">Open {html.escape(label.title())} telemetry</span></a>')
        cards = f'<div class="cards">{"".join(cards_html)}</div>'
    else:
        cards = ('<p class="empty">No household declared yet. Seed the event log '
                 '(see <span class="mono">examples/seed_mission_control.py</span>) '
                 'and reload — this console renders only real, replayed state.</p>')

    # -- evidence behind the hero: standing recommendations and open
    #    vulnerabilities, from the shared Evidence Index via the tile
    #    contract (the same data path RFC-003's home page used),
    #    plus recommendation Claims that concern an active Mission
    #    directly (RFC-004B: the Flight Director needs to know which
    #    corrections address which Mission).
    any_tile = next(iter(tiles.values()), None)
    household_recs = _active_claims(console, any_tile.next_decision) if any_tile else []
    vulnerabilities = _active_claims(console, any_tile.strategic_vulnerability) if any_tile else []
    mission_recs: dict[str, list] = {}
    for mission, _, _ in evaluated:
        mission_recs[mission.id] = _active_claims(console, [
            cid for cid in console.evidence.claims_concerning(mission.id)
            if console.evidence.current_tag(cid, "insight_type") == "recommendation"])
    all_recs = _active_claims(console, {c.id for c in household_recs} |
                              {c.id for claims in mission_recs.values() for c in claims})

    if scope is None:
        risk_value, risk_class = "—", "none"
        corrections_count = "—"
    else:
        if vulnerabilities:
            risk_value, risk_class = f"WATCH · {len(vulnerabilities)} OPEN", "amber"
        else:
            risk_value, risk_class = "LOW", "green"
        corrections_count = str(len(all_recs))

    # -- the "why" line: the evidence-backed sentence under the word.
    if scope is None:
        why = "No household declared yet — this deck renders only real, replayed state."
    elif not missions:
        why = "Declare a Mission to give this Flight Deck something to steer by."
    elif not rags:
        names = ", ".join(m.name for m, _, _ in evaluated)
        why = f"{names}: the target metric cannot be evaluated from the current log."
    else:
        primary_mission, _, primary_result = next(
            (row for row in evaluated if row[1] is not None and
             _RAG_TO_BANNER.get(row[1], ("", ""))[0] == banner_word), evaluated[0])
        label, kind = _METRIC_PRESENTATION.get(
            primary_mission.target_metric, (primary_mission.target_metric, "plain"))
        unit = primary_result.unit_or_currency if primary_result else None
        current = _format_value(
            primary_result.value if primary_result else None, unit, kind)
        if primary_mission.target_range is not None:
            lo, hi = primary_mission.target_range
            why = (f"{primary_mission.name}: {label.lower()} {current} against a "
                   f"target range of {_format_value(lo, unit, kind)}"
                   f"–{_format_value(hi, unit, kind)}.")
        elif primary_mission.target_value is not None:
            why = (f"{primary_mission.name}: {label.lower()} {current} against a target of "
                   f"{_format_value(primary_mission.target_value, unit, kind)}")
            if primary_mission.tolerance:
                why += f" ±{_format_value(primary_mission.tolerance, unit, kind)}"
            why += "."
        else:
            why = f"{primary_mission.name}: no numeric target is declared."

    hero = f"""<section class="hero phase-{_sun_phase(as_of)}" aria-labelledby="flight-status">
  <img class="earthrise" src="{_EARTHRISE_PATH}"
    alt="Earth at sunrise from orbit, its curved horizon lit above the night side"
    width="1774" height="887" fetchpriority="high" decoding="async">
  <div class="scrim"></div>
  <div class="hero-content">
    <p class="eyebrow">FLIGHT PLAN</p>
    <h2 class="flight-word {banner_class}" id="flight-status">{html.escape(banner_word)}</h2>
    <p class="why">{html.escape(why)}</p>
    <div class="hero-stats">
      <div class="stat"><div class="k">STRATEGIC RISK</div>
        <div class="v {risk_class}">{html.escape(risk_value)}</div></div>
      <div class="stat"><div class="k">RECOMMENDED COURSE CORRECTIONS</div>
        <div class="v">{html.escape(corrections_count)}</div></div>
    </div>
  </div>
</section>"""

    # -- Apollo Mission programme: four visual lanes, with real Mission
    #    telemetry rendered only where an active Mission exists. Planned
    #    lanes are explicit UI placeholders and never receive invented values.
    if scope is None:
        missions_html = ('<p class="empty">No household declared yet.</p>')
    else:
        def live_mission_row(mission_number, lane_title, mission, rag, result):
            word, klass = (_RAG_TO_BANNER.get(rag, (rag.upper(), "none"))
                           if rag else ("NOT EVALUABLE", "none"))
            label, kind = _METRIC_PRESENTATION.get(
                mission.target_metric,
                (mission.target_metric.upper() or "—", "plain"))
            unit = result.unit_or_currency if result else None
            value_ok = result is not None and result.status in ("available", "stale")
            value_txt = _format_value(result.value, unit, kind) if value_ok else "—"
            progress = f"{label} {value_txt}"
            if mission.target_range is not None:
                lo, hi = mission.target_range
                progress += (f" · RANGE {_format_value(lo, unit, kind)}"
                             f"–{_format_value(hi, unit, kind)}")
            elif mission.target_value is not None:
                progress += f" · TARGET {_format_value(mission.target_value, unit, kind)}"
                if mission.tolerance:
                    progress += f" ±{_format_value(mission.tolerance, unit, kind)}"
            # RFC-004B: deviation, not completion — honest in both
            # directions, silent when no comparison exists.
            deviation, is_range = _mission_deviation(mission, result)
            variance = _variance_text(deviation, is_range, unit, kind)
            if variance:
                progress += f" · {variance}"
            bar = ""
            if deviation is not None and mission.tolerance:
                bar = _deviation_gauge(
                    deviation, mission.tolerance, klass, is_range=is_range)
            href = (f"/metrics/{mission.target_metric}"
                    if mission.target_metric else "/missions")
            purpose = (f"Tracked against {label.title()}."
                       if mission.name.casefold() == lane_title.casefold() else
                       f"{mission.name} · tracked against {label.title()}.")
            return (
                f'<a class="card mission live" href="{html.escape(href)}">'
                f'<div class="m-number num">{mission_number:02d}</div>'
                f'<div class="m-identity"><div class="m-name">{html.escape(lane_title)}</div>'
                f'<div class="m-purpose">{html.escape(purpose)}</div></div>'
                f'<div class="m-telemetry"><div class="m-progress num">{html.escape(progress)}</div>'
                f'{bar}</div>'
                f'<div class="m-status {klass}">{html.escape(word)}</div>'
                f'<div class="m-link" aria-hidden="true">›</div></a>')

        def planned_mission_row(mission_number, title, description):
            return (
                f'<div class="card mission planned" role="link" aria-disabled="true" '
                f'aria-label="{html.escape(title)}, planned view; target not declared">'
                f'<div class="m-number num">{mission_number:02d}</div>'
                f'<div class="m-identity"><div class="m-name">{html.escape(title)}</div>'
                f'<div class="m-purpose">{html.escape(description)}</div></div>'
                f'<div class="m-telemetry"><div class="m-progress">TARGET NOT DECLARED</div>'
                f'<div class="m-gauge planned" aria-hidden="true"></div></div>'
                f'<div class="m-status">PLANNED</div>'
                f'<div class="m-link unavailable" aria-hidden="true">—</div></div>')

        lane_rows = {}
        unassigned = []
        for row in evaluated:
            lane = _mission_lane(row[0].name)
            if lane is not None and lane not in lane_rows:
                lane_rows[lane] = row
            else:
                unassigned.append(row)

        mission_cards = []
        for mission_number, (lane, title, description) in enumerate(_MISSION_LANES, start=1):
            row = lane_rows.get(lane)
            if row is None:
                mission_cards.append(planned_mission_row(mission_number, title, description))
            else:
                mission_cards.append(live_mission_row(mission_number, title, *row))
        for mission_number, row in enumerate(unassigned, start=len(_MISSION_LANES) + 1):
            mission_cards.append(live_mission_row(mission_number, row[0].name, *row))
        missions_html = f'<div class="missions">{"".join(mission_cards)}</div>'

    # -- Flight Director: at most one evidence-backed recommendation,
    #    and always about the *displayed* state (RFC-004B). Under a
    #    WATCH / OFF COURSE Flight Plan only a recommendation that
    #    concerns the deviating Mission may appear; if none exists, the
    #    panel says so — an unrelated correction under a red banner
    #    would fabricate causality, and absence of advice is a fact
    #    this surface reports like any other.
    director_status = {
        "NOMINAL": "Flight Plan remains nominal.",
        "WATCH": "Flight Plan requires monitoring.",
        "OFF COURSE": "Flight Plan is off course.",
    }.get(banner_word, "Flight Plan status is not yet available.")

    def _rec_panel(latest, lede):
        meta = (f"CONFIDENCE {latest.confidence * 100:.0f}% · "
                f"EVIDENCE ITEMS {len(latest.evidence)} · {_short_date(latest.ts)}")
        return (f'<p class="fd-nominal">{html.escape(director_status)}</p>'
                f'<p class="fd-lede">{html.escape(lede)}</p>'
                f'<div class="panel">'
                f'<p class="fd-statement">{html.escape(latest.statement)}</p>'
                f'<p class="fd-meta">{html.escape(meta)}</p></div>')

    if scope is None:
        director = '<div class="panel"><p class="empty">No household declared yet.</p></div>'
    elif deviating is not None:
        related = mission_recs.get(deviating.id, [])
        if related:
            director = _rec_panel(related[0], f"Course correction for {deviating.name}.")
        else:
            others = len(all_recs)
            note = ""
            if others:
                note = (f" {others} standing recommendation"
                        f"{'s' if others != 1 else ''} on file concern other subjects.")
            director = (
                f'<p class="fd-lede">{html.escape(director_status)}</p>'
                f'<div class="panel">'
                f'<p class="fd-nominal">No course correction on file for '
                f'{html.escape(deviating.name)}.</p>'
                f'<p class="fd-sub">The Flight Director surfaces only evidence-backed '
                f'recommendations that address the deviation — nothing is invented.'
                f'{html.escape(note)}</p></div>')
    elif all_recs:
        latest = all_recs[0]
        director = _rec_panel(latest, "One worthwhile course correction identified.")
    else:
        director = ('<div class="panel"><p class="fd-nominal">Flight Plan remains nominal.</p>'
                    '<p class="fd-sub">No intervention required.</p></div>')

    # -- Recent Course Corrections: the latest reviewed decisions —
    #    Decision Review claims (000 §12) concerning this household.
    corrections = '<p class="empty">No course corrections recorded yet. Reviewed decisions appear here.</p>'
    if scope is not None:
        subjects = {scope.id} | {m.id for m in console.entities.members_of(scope.id)}
        review_ids = [cid for cid in console.evidence.claims_tagged("insight_type", "review")
                      if any(cid in console.evidence.claims_concerning(s) for s in subjects)]
        reviews = _active_claims(console, review_ids)[:4]
        if reviews:
            items = []
            for claim in reviews:
                verdict = console.evidence.current_tag(claim.id, "review_verdict") or "recorded"
                glyph, klass = _VERDICT_GLYPH.get(verdict, ("·", "none"))
                items.append(
                    f'<li><span class="tick {klass}" aria-hidden="true">{glyph}</span>'
                    f'<div><p>{html.escape(claim.statement)}</p>'
                    f'<p class="c-meta">{html.escape(verdict.replace("_", " ").upper())} · '
                    f'{html.escape(_short_date(claim.ts))}</p></div></li>')
            corrections = f'<ul class="corrections">{"".join(items)}</ul>'

    body = f"""{hero}
<section>
  <h2>PRIMARY TELEMETRY</h2>
  {cards}
</section>
<section>
  <h2>APOLLO MISSIONS</h2>
  {missions_html}
</section>
<div class="duo">
<section class="flight-director">
  <h2>FLIGHT DIRECTOR</h2>
  <div class="director-copy">{director}</div>
</section>
<section class="course-corrections">
  <h2>RECENT COURSE CORRECTIONS</h2>
  {corrections}
</section>
</div>
<div class="scope-bar" role="group" aria-label="Financial scope">
  <div class="scope-label">SCOPE</div>
  <button class="active" type="button" aria-pressed="true">HOUSEHOLD<small>ACTIVE</small></button>
  <button type="button" disabled>CHRIS<small>FUTURE SCOPE</small></button>
  <button type="button" disabled>FIONA<small>FUTURE SCOPE</small></button>
  <button type="button" disabled>HAMISH<small>FUTURE SCOPE</small></button>
  <button type="button" disabled>HARRIET<small>FUTURE SCOPE</small></button>
</div>
{_footer(console)}"""
    return _render("Flight Deck", body, as_of, "/")


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

    label, kind = _METRIC_PRESENTATION.get(metric_id, (metric_id.upper(), "plain"))
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
