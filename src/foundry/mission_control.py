"""
Mission Control v0.1 — the first real product surface (RFC-003).

A read-only composition layer over Core's contracts. The division of
responsibility is architectural, not stylistic:

    Finance calculates.   (foundry.finance — never imported here)
    Core evaluates.       (mission_evaluation, compose_tile)
    Mission Control composes.   (this module — no business logic)

Everything on every page arrives through Core contracts: the Metric
Registry (`registry.dispatch`, 000 §13), the Mission Assessment Registry,
and the Flight Deck tile contract (`compose_tile`, 000 §14). This module
never calculates a figure, never owns state, never appends an event, and
never imports a domain's calculation code — the AST test in
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
import math
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
from foundry.core.mission_assessment import (
    MissionAssessment, MissionAssessmentRegistry, MissionAssessmentRequest,
    MissionDefinition,
)
from foundry.core.scope import Subject
from foundry.eventlog import EventLog

router = APIRouter()
DAY = 86_400.0
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


@dataclass
class Console:
    """Everything a page render needs, built by the composition root
    (web.py) — Mission Control itself constructs none of the domain
    wiring and registers nothing with the registry."""
    log: EventLog
    registry: MetricRegistry
    assessments: MissionAssessmentRegistry
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

# Drill-down pages for metrics no longer on the opening screen keep
# their labels and formats here.
_METRIC_PRESENTATION: dict[str, tuple[str, str]] = {
    "finance.net_worth": ("NET WORTH", "currency"),
    "finance.cash_available": ("LIQUIDITY", "currency"),
    "finance.cash_flow": ("NET CASH FLOW", "currency"),
    "finance.liquidity_runway": ("RUNWAY", "months"),
    "finance.employer_concentration": ("EMPLOYER CONCENTRATION", "percent"),
    "finance.debt_ratio": ("DEBT RATIO", "percent"),
    "finance.accessible_assets": ("ACCESSIBLE ASSETS", "currency"),
}

# NASA flight-status vocabulary (Design Constitution): Core's RAG
# evaluation rendered as flight language, never recomputed here.
_RAG_TO_BANNER = {
    "on_track": ("NOMINAL", "green"),
    "achieved": ("NOMINAL", "green"),
    "at_risk": ("WATCH", "amber"),
    "off_track": ("OFF COURSE", "red"),
}

_ASSESSMENT_TO_RAG = {
    "green": "on_track",
    "amber": "at_risk",
    "red": "off_track",
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


def _legacy_scalar_mission_status(
    mission: Mission,
    console: Console,
    scope: Subject,
    as_of: float,
):
    """Deprecated migration adapter for Missions without assessment policy.

    New mission definitions and routes must use MissionAssessmentRegistry.
    """
    return get_mission_status(
        mission.id, console.entities, console.registry, scope, as_of)


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
  .mission-return {{
    display: inline-block; margin-bottom: 22px; pointer-events: auto;
    color: var(--muted); font-size: 9px; font-weight: 650; letter-spacing: .18em;
  }}
  .mission-return:hover {{ color: var(--text); }}
  .mission-empty-state {{
    min-height: 460px; max-width: 640px; padding-top: 112px;
  }}
  .mission-empty-state .status-word {{ margin-bottom: 18px; }}
  .mission-empty-state .empty,
  .mission-empty-state .placeholder {{ max-width: 52ch; line-height: 1.65; }}

  /* -------------------------------- RFC-005 Mission Assessment detail. */
  .mission-detail-hero {{
    min-height: 720px; margin-bottom: 42px; isolation: isolate;
  }}
  .mission-detail-hero img.earthrise {{
    object-position: 57% 62%; filter: saturate(.84) brightness(.86);
    transform: scale(1.42); transform-origin: 58% 0;
  }}
  .mission-detail-hero .scrim {{
    z-index: 1;
    background:
      linear-gradient(90deg, rgba(1,4,8,.97) 0%, rgba(1,4,8,.88) 25%,
        rgba(1,4,8,.34) 49%, rgba(1,4,8,.05) 78%),
      linear-gradient(0deg, rgba(1,4,8,.32) 0%, transparent 38%),
      linear-gradient(180deg, rgba(1,4,8,.18) 0%, transparent 30%);
  }}
  .mission-detail-hero .hero-content {{
    z-index: 3; min-height: 720px; justify-content: center;
    align-items: flex-start; padding: 112px 72px 54px;
    pointer-events: none;
  }}
  .mission-detail-hero .hero-content > * {{ max-width: 390px; }}
  .mission-detail-hero .mission-title {{
    font-size: clamp(50px, 5.3vw, 76px); font-weight: 510;
    letter-spacing: -.035em; line-height: .98; margin: 12px 0 22px;
  }}
  .mission-detail-hero .mission-definition {{
    color: #d2d9e1; font-size: 15px; line-height: 1.62;
  }}
  .mission-hero-meta {{
    display: grid; grid-template-columns: repeat(2, minmax(0,1fr));
    gap: 22px 34px; margin-top: 32px;
  }}
  .mission-hero-meta .margin-stat {{ grid-column: 1 / -1; }}
  .mission-hero-meta .k, .flight-analysis-schedule .k,
  .analysis-rail .k, .telemetry-grid .k {{
    font-size: 9px; font-weight: 650; letter-spacing: .2em; color: var(--faint);
  }}
  .mission-hero-meta .v {{
    margin-top: 4px; font-size: 18px; font-weight: 580; letter-spacing: .06em;
  }}
  .mission-hero-meta .v.green {{ color: var(--green); }}
  .mission-hero-meta .v.amber {{ color: var(--amber); }}
  .mission-hero-meta .v.red {{ color: var(--red); }}
  .mission-hero-meta .v.none {{ color: var(--muted); }}
  .mission-hero-meta .sub {{
    margin-top: 4px; color: #9aa8b6; font-size: 10px; letter-spacing: .04em;
    max-width: 34ch; overflow-wrap: anywhere;
  }}
  .flight-analysis-schedule {{
    display: grid; grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 1px; padding: 1px; margin-bottom: 14px;
    background: var(--line); border: 1px solid var(--line);
  }}
  .flight-analysis-schedule .time-point {{
    min-width: 0; padding: 20px 26px; background: rgba(9,14,20,.72);
  }}
  .flight-analysis-schedule .v {{
    margin-top: 8px; color: var(--text);
    font-size: clamp(18px, 2.1vw, 27px); font-weight: 540;
    letter-spacing: .04em; overflow-wrap: anywhere;
  }}
  .flight-analysis-schedule .sub {{
    margin-top: 7px; color: var(--green); font-size: 11px;
    letter-spacing: .04em; line-height: 1.4; overflow-wrap: anywhere;
  }}
  .hero-trajectory {{
    position: absolute; z-index: 2;
    inset: 62px 20px 104px clamp(470px, 39vw, 520px);
    width: auto; height: auto;
    overflow: visible;
  }}
  .mission-detail-hero.reference-schedule-relocated .hero-trajectory {{
    inset: 48px 12px 34px clamp(470px, 39vw, 520px);
  }}
  .hero-trajectory .actual-path {{
    fill: none; stroke: #edf2f7; stroke-width: 2.1;
    stroke-linecap: round; stroke-linejoin: round;
    filter: drop-shadow(0 0 4px rgba(237,242,247,.3));
  }}
  .hero-trajectory .forecast-path {{
    fill: none; stroke: #d8e1ea; stroke-width: 1.75; stroke-dasharray: 8 7;
    stroke-linecap: round; stroke-linejoin: round;
    filter: drop-shadow(0 0 3px rgba(216,225,234,.22));
  }}
  .hero-trajectory .range-envelope-aura {{
    fill: url(#mission-range-gradient); opacity: .48;
    filter: url(#range-feather-wide);
  }}
  .hero-trajectory .range-envelope-core {{
    fill: url(#mission-range-gradient); opacity: .34;
    filter: url(#range-feather-close);
  }}
  .hero-trajectory .current-halo {{
    fill: rgba(224,168,60,.15); stroke: rgba(237,242,247,.3); stroke-width: 1;
    filter: drop-shadow(0 0 9px rgba(224,168,60,.48));
  }}
  .hero-trajectory .current-node {{
    fill: #070b10; stroke: #edf2f7; stroke-width: 2.2;
    filter: drop-shadow(0 0 8px rgba(224,168,60,.8));
  }}
  .hero-trajectory .current-position {{ outline: none; }}
  .hero-trajectory .current-position:focus-visible .current-node {{
    stroke-width: 3.2; filter: drop-shadow(0 0 10px rgba(237,242,247,.8));
  }}
  .hero-trajectory .mission-milestone {{ outline: none; opacity: .78; }}
  .hero-trajectory .mission-milestone.next-milestone,
  .hero-trajectory .mission-milestone.completion-milestone {{ opacity: .9; }}
  .hero-trajectory .mission-milestone:focus-visible .milestone-ring {{
    stroke-width: 2.2; filter: drop-shadow(0 0 4px currentColor);
  }}
  .hero-trajectory .milestone-stem {{
    stroke: currentColor; stroke-opacity: .28; stroke-width: .75;
  }}
  .hero-trajectory .milestone-ring {{
    fill: #071018; stroke: currentColor; stroke-width: 1.15;
  }}
  .hero-trajectory .milestone-core {{ fill: currentColor; }}
  .hero-trajectory .milestone-label {{
    fill: currentColor; font-size: 8.2px; font-weight: 620; letter-spacing: .9px;
    paint-order: stroke; stroke: rgba(5,8,12,.92); stroke-width: 2.4px;
  }}
  .hero-trajectory .milestone-detail {{
    fill: #8998a6; font-size: 7.4px; letter-spacing: .4px;
    paint-order: stroke; stroke: rgba(5,8,12,.92); stroke-width: 2.2px;
  }}
  .hero-trajectory .current-label,
  .hero-trajectory .current-detail {{
    paint-order: stroke; stroke: rgba(5,8,12,.94); stroke-width: 2.8px;
  }}
  .hero-trajectory .milestone-0 {{ color: #788692; }}
  .hero-trajectory .milestone-1 {{ color: #aa9569; }}
  .hero-trajectory .milestone-2 {{ color: #7692aa; }}
  .hero-trajectory .milestone-3 {{ color: #79a27e; }}

  .analysis-rail {{
    display: grid; grid-template-columns: .8fr .8fr 1.7fr .8fr;
    border: 1px solid var(--line); background: rgba(9,14,20,.72);
  }}
  .analysis-rail .instrument {{ min-width: 0; padding: 24px 26px; }}
  .analysis-rail .instrument + .instrument {{ border-left: 1px solid var(--line); }}
  .analysis-rail .v {{
    margin-top: 8px; font-size: clamp(18px, 2.1vw, 27px);
    font-weight: 540; letter-spacing: .035em;
  }}
  .analysis-rail .recommendation-action .v {{
    font-size: 16px; line-height: 1.45; letter-spacing: 0;
  }}
  .analysis-rail .recommendation-action .sub {{
    color: var(--text); font-size: 14px; font-variant-numeric: tabular-nums;
  }}
  .analysis-rail .sub {{ margin-top: 7px; color: var(--muted); font-size: 11px; }}
  .analysis-rail .green {{ color: var(--green); }}
  .analysis-rail .amber {{ color: var(--amber); }}
  .analysis-rail .red {{ color: var(--red); }}

  details.mission-drilldown {{
    margin-top: 30px; border-block: 1px solid var(--line);
  }}
  details.mission-drilldown > summary {{
    cursor: pointer; list-style: none; padding: 18px 2px;
    color: var(--muted); font-size: 9px; font-weight: 650; letter-spacing: .2em;
  }}
  details.mission-drilldown > summary::-webkit-details-marker {{ display: none; }}
  details.mission-drilldown > summary::after {{
    content: "+"; float: right; color: var(--faint); font-size: 15px; line-height: .8;
  }}
  details.mission-drilldown[open] > summary::after {{ content: "−"; }}
  .mission-drilldown-content {{ padding: 8px 0 26px; }}
  .telemetry-grid {{
    display: grid; grid-template-columns: repeat(3, minmax(0,1fr));
    gap: 1px; background: var(--line); border: 1px solid var(--line);
  }}
  .telemetry-grid .telemetry {{ background: var(--surface); padding: 24px; }}
  .telemetry-grid .value {{ margin-top: 8px; font-size: 26px; }}
  .telemetry-grid .sub {{ margin-top: 7px; color: var(--faint); font-size: 10px; }}
  .assessment-notes {{ margin-top: 30px; border-top: 1px solid var(--line); padding-top: 22px; }}
  .assessment-notes ul {{
    margin: 0 0 0 18px; color: var(--faint); font-size: 12px; line-height: 1.8;
  }}

  @media (max-width: 980px) {{
    .cards {{ grid-template-columns: repeat(2, minmax(0,1fr)); gap: 48px 40px; }}
    .card.mission {{ grid-template-columns: 42px minmax(0,1fr) auto; gap: 14px 18px; }}
    .m-telemetry {{ grid-column: 2 / -1; }}
    .m-link {{ grid-column: 3; grid-row: 1; }}
    .m-status {{ grid-column: 3; grid-row: 2; }}
    .mission-detail-hero .hero-content {{ padding-inline: 44px; }}
    .mission-detail-hero .hero-content > * {{ max-width: 340px; }}
    .hero-trajectory {{
      inset: 72px -18px 116px 390px; transform: none;
    }}
    .mission-detail-hero.reference-schedule-relocated .hero-trajectory {{
      inset: 56px -18px 42px 390px;
    }}
    .flight-analysis-schedule {{
      grid-template-columns: repeat(2, minmax(0,1fr));
    }}
    .analysis-rail {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
    .analysis-rail .instrument:nth-child(3) {{ border-left: 0; border-top: 1px solid var(--line); }}
    .analysis-rail .instrument:nth-child(4) {{ border-top: 1px solid var(--line); }}
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
    .mission-detail-hero {{ min-height: 940px; margin-bottom: 34px; }}
    .mission-empty-state {{ min-height: 380px; padding-top: 92px; }}
    .mission-detail-hero img.earthrise {{
      object-position: 66% 72%; height: 58%; top: 42%;
      transform: scale(1.32); transform-origin: 66% 0;
    }}
    .mission-detail-hero .scrim {{
      background:
        linear-gradient(180deg, rgba(1,4,8,.96) 0%, rgba(1,4,8,.9) 39%,
          rgba(1,4,8,.28) 68%, rgba(1,4,8,.08) 100%),
        linear-gradient(90deg, rgba(1,4,8,.34), transparent);
    }}
    .mission-detail-hero .hero-content {{
      min-height: auto; height: 510px; justify-content: flex-start;
      padding: 92px 24px 18px;
    }}
    .mission-detail-hero .hero-content > * {{ max-width: none; }}
    .mission-detail-hero .mission-title {{
      font-size: clamp(42px, 12.5vw, 58px); max-width: 8ch;
    }}
    .mission-detail-hero .mission-definition {{ font-size: 14px; max-width: 38ch; }}
    .mission-hero-meta {{ grid-template-columns: repeat(3, minmax(0,1fr)); gap: 16px; margin-top: 24px; }}
    .mission-hero-meta .margin-stat {{ grid-column: auto; }}
    .mission-hero-meta .v {{ font-size: 14px; letter-spacing: .03em; }}
    .mission-hero-meta .sub {{ display: none; }}
    .hero-trajectory {{
      inset: 510px -30px 150px -58px; width: auto; height: auto;
      transform: none;
    }}
    .hero-trajectory .milestone-detail {{ opacity: 0; }}
    .hero-trajectory .mission-milestone:not(.next-milestone):not(.completion-milestone)
      .milestone-label {{ opacity: 0; }}
    .hero-trajectory .mission-milestone:focus .milestone-detail,
    .hero-trajectory .mission-milestone:hover .milestone-detail {{
      opacity: 1; paint-order: stroke; stroke: #05080c; stroke-width: 3px;
    }}
    .hero-trajectory .mission-milestone:focus .milestone-label,
    .hero-trajectory .mission-milestone:hover .milestone-label {{
      opacity: 1; paint-order: stroke; stroke: #05080c; stroke-width: 3px;
    }}
    .hero-trajectory .milestone-label {{ font-size: 14px; stroke-width: 4px; }}
    .hero-trajectory .current-label,
    .hero-trajectory .current-detail {{ opacity: 0; }}
    .mission-detail-hero.reference-schedule-relocated {{
      min-height: 820px;
    }}
    .mission-detail-hero.reference-schedule-relocated .hero-trajectory {{
      inset: 500px -30px 28px -58px;
    }}
    .flight-analysis-schedule {{ grid-template-columns: 1fr; }}
    .flight-analysis-schedule .time-point {{ padding: 20px 22px; }}
    .analysis-rail {{ grid-template-columns: 1fr; }}
    .analysis-rail .instrument + .instrument {{
      border-left: 0; border-top: 1px solid var(--line);
    }}
    .analysis-rail .instrument:nth-child(3),
    .analysis-rail .instrument:nth-child(4) {{ border-top: 1px solid var(--line); }}
    .telemetry-grid {{ grid-template-columns: 1fr; }}
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
    definitions = console.assessments.definitions()

    # -- Core evaluates every active Mission; this page only renders.
    evaluated = []  # (mission, rag, result)
    assessments_by_mission: dict[str, MissionAssessment] = {}
    if scope is not None:
        for mission in missions:
            if mission.assessment_policy_id:
                assessment = console.assessments.dispatch(MissionAssessmentRequest(
                    mission_id=mission.id, policy_id=mission.assessment_policy_id,
                    scope=scope, as_of=as_of))
                assessments_by_mission[mission.id] = assessment
                rag = _ASSESSMENT_TO_RAG.get(assessment.status)
                result = assessment.current_value
            else:
                rag, result = _legacy_scalar_mission_status(
                    mission, console, scope, as_of)
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
        primary_assessment = assessments_by_mission.get(primary_mission.id)
        label, kind = (
            _assessment_current_presentation(primary_assessment)
            if primary_assessment is not None else
            _METRIC_PRESENTATION.get(
                primary_mission.target_metric, ("CURRENT VALUE", "plain"))
        )
        unit = primary_result.unit_or_currency if primary_result else None
        current = _format_value(
            primary_result.value if primary_result else None, unit, kind)
        if primary_assessment is not None:
            milestone = (
                primary_assessment.current_milestone.label
                if primary_assessment.current_milestone else "not evaluable")
            completion = next((
                item for item in primary_assessment.milestones
                if item.completes_mission), None)
            if completion is not None and primary_assessment.eta is not None:
                comparison = _time_gain_phrase(
                    primary_assessment.delta_v.months
                    if primary_assessment.delta_v else None,
                    primary_assessment.delta_v.direction
                    if primary_assessment.delta_v else None,
                )
                why = (
                    f"{completion.label} by "
                    f"{_month_year(primary_assessment.eta).title()}, "
                    f"{comparison}. {label.title()} is {current}; "
                    f"{milestone} is the current milestone. Further "
                    "acceleration is assessed separately from the next "
                    "recommended burn.")
            else:
                trajectory = (
                    primary_assessment.trajectory_state or "not evaluable")
                why = (
                    f"{label.title()} is {current}. {milestone} is the "
                    f"current milestone; trajectory is {trajectory}.")
        elif primary_mission.target_range is not None:
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
        def live_mission_row(
            mission_number,
            title,
            mission,
            rag,
            result,
            definition: MissionDefinition | None = None,
        ):
            assessment = assessments_by_mission.get(mission.id)
            if assessment is not None:
                word = assessment.trajectory_state.upper() \
                    if assessment.trajectory_state else "NOT EVALUABLE"
                klass = (
                    assessment.trajectory_tone
                    if assessment.trajectory_tone in ("green", "amber", "red")
                    else "none")
            else:
                word, klass = (_RAG_TO_BANNER.get(rag, (rag.upper(), "none"))
                               if rag else ("NOT EVALUABLE", "none"))
            label, kind = (
                _assessment_current_presentation(assessment)
                if assessment is not None else
                _METRIC_PRESENTATION.get(
                    mission.target_metric, ("CURRENT VALUE", "plain"))
            )
            unit = result.unit_or_currency if result else None
            value_ok = result is not None and result.status in ("available", "stale")
            value_txt = _format_value(result.value, unit, kind) if value_ok else "—"
            progress = f"{label} {value_txt}"
            if assessment is not None:
                milestone = (
                    assessment.current_milestone.label
                    if assessment.current_milestone else "NOT EVALUABLE")
                progress += f" · CURRENT MILESTONE {milestone.upper()}"
                margin = assessment.mission_margin
                if margin and margin.state:
                    progress += f" · MISSION MARGIN {margin.state.upper()}"
            elif mission.target_range is not None:
                lo, hi = mission.target_range
                progress += (f" · RANGE {_format_value(lo, unit, kind)}"
                             f"–{_format_value(hi, unit, kind)}")
            elif mission.target_value is not None:
                progress += f" · TARGET {_format_value(mission.target_value, unit, kind)}"
                if mission.tolerance:
                    progress += f" ±{_format_value(mission.tolerance, unit, kind)}"
            # RFC-004B: deviation, not completion — honest in both
            # directions, silent when no comparison exists.
            deviation, is_range = (
                (None, False) if assessment is not None
                else _mission_deviation(mission, result))
            variance = (
                "" if assessment is not None
                else _variance_text(deviation, is_range, unit, kind))
            if variance:
                progress += f" · {variance}"
            bar = ""
            if deviation is not None and mission.tolerance:
                bar = _deviation_gauge(
                    deviation, mission.tolerance, klass, is_range=is_range)
            href = (
                f"/missions/{definition.slug}" if definition is not None else
                f"/metrics/{mission.target_metric}"
                if mission.target_metric else "/missions")
            purpose = (
                definition.definition
                if definition is not None and definition.definition else
                f"{mission.name} · tracked against {label.title()}."
            )
            return (
                f'<a class="card mission live" href="{html.escape(href)}">'
                f'<div class="m-number num">{mission_number:02d}</div>'
                f'<div class="m-identity"><div class="m-name">{html.escape(title)}</div>'
                f'<div class="m-purpose">{html.escape(purpose)}</div></div>'
                f'<div class="m-telemetry"><div class="m-progress num">{html.escape(progress)}</div>'
                f'{bar}</div>'
                f'<div class="m-status {klass}">TRAJECTORY · {html.escape(word)}</div>'
                f'<div class="m-link" aria-hidden="true">›</div></a>')

        def planned_mission_row(mission_number, definition):
            description = (
                definition.definition or
                "Assessment and target are planned.")
            return (
                f'<a class="card mission planned" '
                f'href="/missions/{html.escape(definition.slug)}" '
                f'aria-label="{html.escape(definition.label)}, planned view; '
                f'target not declared">'
                f'<div class="m-number num">{mission_number:02d}</div>'
                f'<div class="m-identity"><div class="m-name">'
                f'{html.escape(definition.label)}</div>'
                f'<div class="m-purpose">{html.escape(description)}</div></div>'
                f'<div class="m-telemetry"><div class="m-progress">TARGET NOT DECLARED</div>'
                f'<div class="m-gauge planned" aria-hidden="true"></div></div>'
                f'<div class="m-status">PLANNED</div>'
                f'<div class="m-link unavailable" aria-hidden="true">›</div></a>')

        def ambiguous_mission_row(mission_number, definition):
            return (
                f'<a class="card mission live" '
                f'href="/missions/{html.escape(definition.slug)}">'
                f'<div class="m-number num">{mission_number:02d}</div>'
                f'<div class="m-identity"><div class="m-name">'
                f'{html.escape(definition.label)}</div>'
                f'<div class="m-purpose">Multiple active Missions claim this '
                f'definition; no Mission was selected.</div></div>'
                f'<div class="m-telemetry"><div class="m-progress">'
                f'AMBIGUOUS ACTIVE MISSION</div></div>'
                f'<div class="m-status none">NOT EVALUABLE</div>'
                f'<div class="m-link unavailable" aria-hidden="true">›</div></a>')

        definition_rows: dict[str, list] = {}
        legacy_rows = []
        for row in evaluated:
            definition = (
                console.assessments.definition_for_policy(
                    row[0].assessment_policy_id)
                if row[0].assessment_policy_id else None
            )
            if definition is not None:
                definition_rows.setdefault(definition.slug, []).append(row)
            else:
                legacy_rows.append(row)

        mission_cards = []
        for mission_number, definition in enumerate(definitions, start=1):
            rows = definition_rows.get(definition.slug, [])
            if not rows:
                mission_cards.append(
                    planned_mission_row(mission_number, definition))
            elif len(rows) > 1:
                mission_cards.append(
                    ambiguous_mission_row(mission_number, definition))
            else:
                mission_cards.append(live_mission_row(
                    mission_number, definition.label, *rows[0], definition))
        for mission_number, row in enumerate(
            legacy_rows, start=len(definitions) + 1
        ):
            mission_cards.append(
                live_mission_row(mission_number, row[0].name, *row))
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
<section id="missions">
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


def _month_year(ts: float | None) -> str:
    if ts is None:
        return "NOT IN HORIZON"
    try:
        utc = time.gmtime(ts)
    except (OSError, OverflowError, ValueError):
        return "NOT EVALUABLE"
    return f"{MONTH_NAMES[utc.tm_mon - 1]} {utc.tm_year}".upper()


def _format_month_delta(months: int | None, direction: str | None) -> str:
    """Render the Finance-declared month resolution without extra precision."""
    if months is None or direction not in ("accelerated", "delayed"):
        return "NOT AVAILABLE"
    magnitude = abs(months)
    if magnitude == 0:
        return f"LESS THAN 1 MONTH {direction.upper()}"
    noun = "MONTH" if magnitude == 1 else "MONTHS"
    return f"ABOUT {magnitude} {noun} {direction.upper()}"


def _time_gain_phrase(months: int | None, direction: str | None) -> str:
    """Plain-language, month-resolution comparison from provider output."""
    if months is None or direction not in ("accelerated", "delayed"):
        return "timing against the reference schedule is not available"
    magnitude = abs(months)
    years, remaining_months = divmod(magnitude, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if remaining_months or not parts:
        parts.append(
            f"{remaining_months} month"
            f"{'s' if remaining_months != 1 else ''}")
    relation = "ahead of" if direction == "accelerated" else "behind"
    return f"around {' '.join(parts)} {relation} the reference schedule"


def _assessment_current_presentation(
    assessment: MissionAssessment,
) -> tuple[str, str]:
    """Use provider presentation metadata, never a raw metric identifier."""
    current = assessment.current_value
    if current is not None:
        for item in assessment.telemetry:
            if item.result.metric_id == current.metric_id:
                return item.label, item.format_kind
    return "CURRENT VALUE", "plain"


def _smooth_svg_path(points: tuple[tuple[float, float], ...]) -> str:
    if not points:
        return ""
    if len(points) == 1:
        return f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    commands = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for index in range(1, len(points) - 1):
        control = points[index]
        following = points[index + 1]
        midpoint = (
            (control[0] + following[0]) / 2.0,
            (control[1] + following[1]) / 2.0,
        )
        commands.append(
            f"Q{control[0]:.1f},{control[1]:.1f} "
            f"{midpoint[0]:.1f},{midpoint[1]:.1f}")
    final = points[-1]
    commands.append(f"T{final[0]:.1f},{final[1]:.1f}")
    return " ".join(commands)


def _orbital_point(progress: float) -> tuple[float, float]:
    """A visual mission arc, explicitly not a scientific orbit."""
    progress = max(0.0, min(progress, 1.03))
    inverse = 1.0 - progress
    p0, p1, p2, p3 = (
        (305.0, 455.0),
        (445.0, 335.0),
        (760.0, 105.0),
        (950.0, 118.0),
    )
    return (
        inverse ** 3 * p0[0]
        + 3.0 * inverse ** 2 * progress * p1[0]
        + 3.0 * inverse * progress ** 2 * p2[0]
        + progress ** 3 * p3[0],
        inverse ** 3 * p0[1]
        + 3.0 * inverse ** 2 * progress * p1[1]
        + 3.0 * inverse * progress ** 2 * p2[1]
        + progress ** 3 * p3[1],
    )


def _polygon_area(points: tuple[tuple[float, float], ...]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, (*points[1:], points[0]))
    )) / 2.0


def _mission_trajectory_geometry(assessment: MissionAssessment) -> dict:
    """Map immutable assessment values to honest two-dimensional geometry."""
    current_value = (
        assessment.current_value.value
        if assessment.current_value and assessment.current_value.value is not None
        else 0.0
    )
    milestones = assessment.milestones
    direction = (
        assessment.current_milestone.destination_direction
        if assessment.current_milestone is not None else
        milestones[0].destination_direction if milestones else
        "higher_is_better"
    )

    def directed(value: float) -> float:
        return value if direction == "higher_is_better" else -value

    actual_values = [
        item.value for item in assessment.trajectory
        if math.isfinite(item.value)
    ]
    current_progress_value = directed(current_value)
    actual_start = min(
        [directed(value) for value in actual_values] or [current_progress_value])
    milestone_bounds = [
        directed(bound) for milestone in milestones
        for bound in (
            milestone.lower_bound,
            milestone.upper_bound,
            milestone.target_value,
        )
        if bound is not None and math.isfinite(bound)
    ]
    forecast_values = [
        directed(value) for point in assessment.forecast
        for value in (point.low, point.base, point.high)
        if math.isfinite(value)
    ]
    # The mission arc ends at its declared destination. Forecast values
    # beyond it must not compress every milestone into an unreadable cluster;
    # without milestones, the forecast itself defines the visual scale.
    scale_values = milestone_bounds if milestone_bounds else forecast_values
    mission_scale = max(
        [current_progress_value, *scale_values, current_progress_value + 1.0])
    current_transition = 0.38

    def progress_for(value: float) -> float:
        progress_value = directed(value)
        if progress_value <= current_progress_value:
            span = max(current_progress_value - actual_start, 1.0)
            return max(0.0, min(
                (progress_value - actual_start) / span, 1.0)
            ) * current_transition
        span = max(mission_scale - current_progress_value, 1.0)
        future_progress = max(0.0, min(
            (progress_value - current_progress_value) / span, 1.06))
        return current_transition + future_progress * (1.0 - current_transition)

    def point_for(value: float) -> tuple[float, float]:
        return _orbital_point(progress_for(value))

    valid_forecast = tuple(
        point for point in assessment.forecast
        if all(math.isfinite(value) for value in (
            point.low, point.base, point.high))
        and point.low <= point.base <= point.high
    )
    partial = len(valid_forecast) != len(assessment.forecast)
    actual_points = tuple(point_for(value) for value in actual_values)
    base_points = tuple(point_for(point.base) for point in valid_forecast)
    spreads = tuple(point.high - point.low for point in valid_forecast)
    maximum_spread = max(spreads or (0.0,))
    low_points: tuple[tuple[float, float], ...] = ()
    high_points: tuple[tuple[float, float], ...] = ()
    range_status = "unavailable" if not valid_forecast else "collapsed"
    if len(valid_forecast) >= 2 and maximum_spread > 0.0:
        pixels_per_unit = 54.0 / maximum_spread
        low_points = tuple(
            (base_x, base_y + (point.base - point.low) * pixels_per_unit)
            for point, (base_x, base_y) in zip(valid_forecast, base_points)
        )
        high_points = tuple(
            (base_x, base_y - (point.high - point.base) * pixels_per_unit)
            for point, (base_x, base_y) in zip(valid_forecast, base_points)
        )
        range_status = "partial" if partial else "available"
    elif valid_forecast and maximum_spread > 0.0:
        # A single point can have vertical width but cannot define an
        # honest two-dimensional corridor.
        range_status = "unavailable"
    boundary = (
        (*low_points, *reversed(high_points))
        if low_points and high_points else ()
    )
    range_path = (
        "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in boundary) + " Z"
        if boundary else ""
    )
    return {
        "actual_points": actual_points,
        "base_points": base_points,
        "low_points": low_points,
        "high_points": high_points,
        "actual_path": _smooth_svg_path(actual_points),
        "forecast_path": _smooth_svg_path(base_points),
        "range_path": range_path,
        "range_area": _polygon_area(tuple(boundary)),
        "range_widths": tuple(
            low[1] - high[1] for low, high in zip(low_points, high_points)),
        "range_status": range_status,
        "current_point": point_for(current_value),
        "phase_points": tuple(
            (milestone, point_for(milestone.target_value))
            for milestone in sorted(milestones, key=lambda item: item.order)
        ),
    }


def _milestone_range_text(milestone) -> str:
    unit = milestone.unit_or_currency
    format_kind = "months" if unit == "months" else "currency"
    if milestone.upper_bound is None:
        return (
            f"ABOVE "
            f"{_format_value(milestone.lower_bound, unit, format_kind)}")
    if milestone.lower_bound <= 0:
        return (
            f"BELOW "
            f"{_format_value(milestone.upper_bound, unit, format_kind)}")
    return (
        f"{_format_value(milestone.lower_bound, unit, format_kind)} – "
        f"{_format_value(milestone.upper_bound, unit, format_kind)}"
    )


def _mission_trajectory_svg(assessment: MissionAssessment) -> str:
    if assessment.applicability.trajectory == "not_applicable":
        return ""
    if assessment.applicability.trajectory == "unavailable":
        return (
            '<p class="empty">Trajectory unavailable. '
            'Trajectory history is not available for this mission.</p>')
    geometry = _mission_trajectory_geometry(assessment)
    if not geometry["actual_path"] and not geometry["forecast_path"]:
        return '<p class="empty">Trajectory unavailable.</p>'

    current_value = (
        assessment.current_value.value
        if assessment.current_value and assessment.current_value.value is not None
        else None
    )
    current_unit = (
        assessment.current_value.unit_or_currency
        if assessment.current_value else None)
    current_metric_label, current_format_kind = (
        _assessment_current_presentation(assessment))
    current_milestone = (
        assessment.current_milestone.label
        if assessment.current_milestone else "Not evaluable")
    current_x, current_y = geometry["current_point"]
    range_path = geometry["range_path"]
    range_svg = (
        f'<path class="range-envelope-aura" d="{range_path}" aria-hidden="true"/>'
        f'<path class="range-envelope-core" d="{range_path}" aria-hidden="true"/>'
        if range_path else "")
    actual_svg = (
        f'<path class="actual-path" d="{geometry["actual_path"]}" '
        f'aria-hidden="true"/>' if geometry["actual_path"] else "")
    forecast_svg = (
        f'<path class="forecast-path" d="{geometry["forecast_path"]}" '
        f'aria-hidden="true"/>' if geometry["forecast_path"] else "")

    future_milestones = [
        milestone for milestone in assessment.milestones
        if (
            milestone.target_value > (current_value or 0.0)
            if milestone.destination_direction == "higher_is_better"
            else milestone.target_value < (current_value or 0.0)
        )
    ]
    next_milestone_id = (
        min(future_milestones, key=lambda milestone: milestone.order).id
        if future_milestones else None)
    milestone_svg = []
    for milestone, (x, y) in geometry["phase_points"]:
        label_lane = milestone.order % 2
        classes = [
            "mission-milestone",
            f"milestone-{milestone.order % 4}",
            f"label-lane-{label_lane}",
        ]
        if milestone.id == next_milestone_id:
            classes.append("next-milestone")
        if milestone.completes_mission:
            classes.append("completion-milestone")
        if milestone.is_current:
            classes.append("current-phase")
        stem_offset = -42.0 if label_lane == 0 else -68.0
        stem_end = y + stem_offset
        label_y = stem_end - 12.0
        detail_y = label_y + 13.0
        anchor = (
            "end"
            if milestone.order in (0, len(assessment.milestones) - 1)
            else "middle"
        )
        label_x = (
            x - 24.0
            if milestone.order == len(assessment.milestones) - 1 else
            x - 4.0 if anchor == "end" else x
        )
        context = "Current milestone. " if milestone.is_current else ""
        completion = (
            "Mission completion milestone. "
            if milestone.completes_mission else "")
        eta = (
            f"Estimated {_month_year(milestone.estimated_at)}. "
            if milestone.estimated_at is not None else "")
        accessible_name = (
            f"{milestone.label}. {context}{completion}"
            f"{_milestone_range_text(milestone)}. {eta}"
        )
        milestone_svg.append(f"""<g class="{" ".join(classes)}" tabindex="0"
    role="group" aria-label="{html.escape(accessible_name)}">
    <line class="milestone-stem" x1="{x:.1f}" y1="{y:.1f}"
      x2="{x:.1f}" y2="{stem_end:.1f}"/>
    <circle class="milestone-ring" cx="{x:.1f}" cy="{y:.1f}" r="5.5"/>
    <circle class="milestone-core" cx="{x:.1f}" cy="{y:.1f}" r="1.8"/>
    <text class="milestone-label" x="{label_x:.1f}" y="{label_y:.1f}"
      text-anchor="{anchor}">{html.escape(milestone.label.upper())}</text>
    <text class="milestone-detail" x="{label_x:.1f}" y="{detail_y:.1f}"
      text-anchor="{anchor}">{html.escape(_milestone_range_text(milestone))}</text>
  </g>""")

    current_label = (
        f"Today. {current_metric_label} "
        f"{_format_value(current_value, current_unit, current_format_kind)}. "
        f"Current milestone {current_milestone}. Trajectory "
        f"{assessment.trajectory_state or 'not evaluable'}."
    )
    range_description = {
        "available": (
            "A low to high sensitivity corridor widens as the calculated "
            "forecast paths diverge. It is not a probability."),
        "partial": (
            "A partial low to high sensitivity corridor is shown for valid "
            "forecast points only. It is not a probability."),
        "collapsed": (
            "Low and high forecast paths are identical, so no sensitivity "
            "corridor is drawn."),
        "unavailable": "Low and high sensitivity geometry is unavailable.",
    }[geometry["range_status"]]
    return f"""<svg class="trajectory-svg hero-trajectory" viewBox="0 0 1000 600"
      role="group" aria-labelledby="trajectory-title trajectory-description"
      data-range-status="{geometry["range_status"]}"
      preserveAspectRatio="xMidYMid meet">
  <title id="trajectory-title">Mission trajectory</title>
  <desc id="trajectory-description">A solid historical path reaches the current position
  at {html.escape(_format_value(
      current_value, current_unit, current_format_kind))}. A dashed expected forecast
  continues along the mission arc. {html.escape(range_description)}</desc>
  <defs>
    <linearGradient id="mission-range-gradient" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#6d879f" stop-opacity=".02"/>
      <stop offset=".55" stop-color="#7e9cb7" stop-opacity=".14"/>
      <stop offset="1" stop-color="#b2c2d0" stop-opacity=".26"/>
    </linearGradient>
    <filter id="range-feather-wide" x="-22%" y="-35%" width="144%" height="170%">
      <feGaussianBlur stdDeviation="10"/>
    </filter>
    <filter id="range-feather-close" x="-12%" y="-20%" width="124%" height="140%">
      <feGaussianBlur stdDeviation="3.2"/>
    </filter>
  </defs>
  {range_svg}
  {actual_svg}
  {forecast_svg}
  <g class="current-position" tabindex="0" role="group"
    aria-label="{html.escape(current_label)}">
    <circle class="current-halo" cx="{current_x:.1f}" cy="{current_y:.1f}" r="19"/>
    <circle class="current-node" cx="{current_x:.1f}" cy="{current_y:.1f}" r="7.5"/>
    <circle cx="{current_x:.1f}" cy="{current_y:.1f}" r="2.5" fill="#e0a83c"/>
    <text class="current-label" x="{current_x + 17:.1f}"
      y="{current_y - 22:.1f}" fill="#edf2f7"
      font-size="10.5" font-weight="700" letter-spacing="1.1">TODAY</text>
    <text class="current-detail" x="{current_x + 17:.1f}"
      y="{current_y - 8:.1f}" fill="#b8c3ce"
      font-size="8.5" letter-spacing=".5">{html.escape(_format_value(
          current_value, current_unit, current_format_kind))}</text>
  </g>
  {"".join(milestone_svg)}
</svg>"""


@dataclass(frozen=True)
class _MissionHeroView:
    """Escaped-at-render presentation inputs for the shared mission hero."""

    title: str
    definition: str
    return_link: str
    sun_phase: str
    reference_schedule_class: str
    trajectory: str
    milestone_label: str
    trajectory_tile: str
    eta_tile: str
    margin_value: str
    margin_sub: str
    accessible_summary: str


@dataclass(frozen=True)
class _FlightAnalysisView:
    """Presentation inputs shared by every live Mission Detail analysis."""

    schedule: str
    delta_instrument: str
    milestone_completion: float
    milestone_label: str
    recommendation_action: str
    recommendation_amount: str
    recommendation_delta_instrument: str


@dataclass(frozen=True)
class _MissionDataView:
    """Presentation inputs for shared telemetry and provenance disclosure."""

    telemetry_cards: tuple[str, ...]
    recommendation_detail: str
    note_items: str
    input_reference_count: int
    assumption_reference_count: int


def _render_mission_hero(view: _MissionHeroView) -> str:
    return f"""<section class="hero mission-detail-hero{view.reference_schedule_class} phase-{html.escape(view.sun_phase)}"
  aria-labelledby="mission-title" aria-describedby="trajectory-summary">
  <img class="earthrise" src="{_EARTHRISE_PATH}"
    alt="Earth at sunrise from orbit, its curved horizon lit above the night side"
    width="1774" height="887" fetchpriority="high" decoding="async">
  <div class="scrim"></div>
  {view.trajectory}
  <div class="hero-content">
    {view.return_link}
    <p class="eyebrow">MISSION</p>
    <h2 class="mission-title" id="mission-title">{html.escape(view.title)}</h2>
    <p class="mission-definition">{html.escape(view.definition)}</p>
    <div class="mission-hero-meta">
      <div><p class="k">CURRENT MILESTONE</p><p class="v">{html.escape(view.milestone_label)}</p></div>
      {view.trajectory_tile}
      {view.eta_tile}
      <div class="margin-stat"><p class="k">MISSION MARGIN</p>
        <p class="v num">{html.escape(view.margin_value)}</p>
        <p class="sub">{html.escape(view.margin_sub)}</p></div>
    </div>
  </div>
  {view.accessible_summary}
</section>"""


def _render_flight_analysis(view: _FlightAnalysisView) -> str:
    return f"""<section aria-labelledby="analysis-heading">
  <h2 id="analysis-heading">FLIGHT ANALYSIS</h2>
  {view.schedule}
  <div class="analysis-rail">
    {view.delta_instrument}
    <div class="instrument"><p class="k">MILESTONE COMPLETION</p>
      <p class="v num">{view.milestone_completion:.1f}%</p>
      <p class="sub">{html.escape(view.milestone_label)}</p></div>
    <div class="instrument recommendation-action"><p class="k">NEXT BURN</p>
      <p class="v">{html.escape(view.recommendation_action)}</p>
      <p class="sub">{html.escape(view.recommendation_amount)}</p></div>
    {view.recommendation_delta_instrument}
  </div>
</section>"""


def _render_mission_data(view: _MissionDataView) -> str:
    return f"""<section>
  <details class="mission-drilldown">
    <summary>DEEPER MISSION DATA · TELEMETRY, ASSUMPTIONS &amp; PROVENANCE</summary>
    <div class="mission-drilldown-content">
      <h2>PRIMARY TELEMETRY</h2>
      <div class="telemetry-grid">{"".join(view.telemetry_cards)}</div>
      <div class="assessment-notes">
        <h2>ASSUMPTIONS, LIMITATIONS &amp; PROVENANCE</h2>
        <ul>{view.recommendation_detail}{view.note_items}
          <li>{view.input_reference_count} metric input reference(s)</li>
          <li>{view.assumption_reference_count} Assumption Set reference(s)</li>
        </ul>
      </div>
    </div>
  </details>
</section>"""


@router.get("/missions/{slug}", response_class=HTMLResponse)
def mission_detail(request: Request, slug: str):
    if session_email(request) is None:
        return _login_redirect()
    console = _console(request)
    as_of = _as_of(console)
    mission_return = (
        '<a class="mission-return" href="/#missions">← ALL MISSIONS</a>')
    definition = console.assessments.definition_for_slug(slug)
    if definition is None:
        response = _render(
            "Mission not found",
            f"""<section class="mission-empty-state">{mission_return}
  <h2>MISSION NOT FOUND</h2>
  <p class="empty">This mission is not available.</p>
</section>""" + _footer(console),
            as_of,
            "/missions",
        )
        response.status_code = 404
        return response

    if definition.assessment_policy_id is None:
        body = f"""<section class="mission-empty-state">{mission_return}
  <h2>{html.escape(definition.label.upper())}</h2>
  <div class="status-word none">PLANNED</div>
  <p class="empty">This mission is planned. Its assessment is not available yet.</p>
  <p class="placeholder">No target, tracking criteria, or mission status is shown.</p>
</section>{_footer(console)}"""
        return _render(definition.label, body, as_of, "/missions")

    scope = _household_scope(console)
    matching_missions = [
        mission for mission in _active_missions(console)
        if mission.assessment_policy_id == definition.assessment_policy_id
    ]
    if len(matching_missions) > 1:
        body = f"""<section class="mission-empty-state">{mission_return}
  <h2>{html.escape(definition.label.upper())}</h2>
  <div class="status-word none">NOT EVALUABLE</div>
  <p class="empty">We cannot assess this mission because more than one active
  mission is configured.</p>
  <p class="placeholder">No mission was selected.</p>
</section>{_footer(console)}"""
        return _render(definition.label, body, as_of, "/missions")
    mission = matching_missions[0] if matching_missions else None
    if scope is None or mission is None:
        body = f"""<section class="mission-empty-state">{mission_return}
  <h2>{html.escape(definition.label.upper())}</h2>
  <p class="empty">This mission has not been set up yet.</p>
  <p class="placeholder">No assessment is shown until its goal and household
  are available.</p>
</section>""" + _footer(console)
        return _render(definition.label, body, as_of, "/missions")

    assessment = console.assessments.dispatch(MissionAssessmentRequest(
        mission_id=mission.id, policy_id=definition.assessment_policy_id,
        scope=scope, as_of=as_of))
    if assessment.status == "unavailable" or assessment.current_value is None:
        limitations = "".join(
            f"<li>{html.escape(note)}</li>" for note in assessment.limitations)
        body = f"""<section class="mission-empty-state">{mission_return}
  <h2>{html.escape(definition.label.upper())}</h2>
  <div class="status-word none">NOT EVALUABLE</div>
  <p class="status-sub">We cannot assess this mission right now. No mission
  status is shown because the available data could not be evaluated safely.</p>
  <ul style="margin:24px 0 0 18px;color:var(--muted);">{limitations}</ul>
</section>{_footer(console)}"""
        return _render(definition.label, body, as_of, "/missions")

    milestone = assessment.current_milestone
    trajectory_class = (
        assessment.trajectory_tone
        if assessment.trajectory_tone in ("green", "amber", "red")
        else "none"
    )
    eta = _month_year(assessment.eta)
    milestone_label = (
        milestone.label.upper() if milestone else "NOT EVALUABLE")
    completion_milestone = next(
        (item for item in assessment.milestones if item.completes_mission), None)
    completion_label = (
        completion_milestone.label.upper()
        if completion_milestone else "MISSION COMPLETION")
    trajectory_label = (
        assessment.trajectory_state.upper()
        if assessment.trajectory_state else "NOT EVALUABLE")
    milestone_completion = milestone.completion * 100.0 if milestone else 0.0
    margin = assessment.mission_margin
    margin_value = margin.state.upper() if margin and margin.state else "—"
    margin_sub = margin.description if margin else "Not available"
    if margin and margin.pace_percent is not None:
        margin_sub = f"{margin.pace_percent:+.1f}% · {margin_sub}"
    delta_v = assessment.delta_v
    delta_value = _format_month_delta(
        delta_v.months if delta_v else None,
        delta_v.direction if delta_v else None)
    delta_sub = delta_v.description if delta_v else "Not available"

    recommendation = (
        assessment.recommendations[0] if assessment.recommendations else None)
    if recommendation is None:
        recommendation_action = "No scenario-modelled action is available."
        recommendation_amount = "No declared intervention"
        recommendation_impact = "NOT AVAILABLE"
        recommendation_detail = (
            "<li>No improving recommendation is declared.</li>")
    elif recommendation.status != "available" \
            or recommendation.amount is None \
            or recommendation.unit_or_currency is None \
            or not recommendation.action_label:
        recommendation_action = "Recommendation unavailable"
        recommendation_amount = "Recommendation evidence is incomplete"
        recommendation_impact = "NOT AVAILABLE"
        recommendation_detail = "".join(
            f"<li>{html.escape(note)}</li>"
            for note in (
                *recommendation.limitations,
                "The declared recommendation evidence is incomplete.",
            ))
    else:
        recommendation_action = recommendation.action_label
        amount = _format_value(
            recommendation.amount, recommendation.unit_or_currency, "currency")
        recommendation_amount = (
            f"{amount} per {recommendation.cadence}"
            if recommendation.cadence else amount)
        recommendation_impact = _format_month_delta(
            recommendation.estimated_delta_v_months,
            recommendation.delta_v_direction)
        if assessment.applicability.delta_v == "not_applicable":
            recommendation_lineage = (
                f"Declared scenario with "
                f"{len(recommendation.assumption_references)} "
                "assumption reference(s) and "
                f"{len(recommendation.evidence_references)} "
                "evidence reference(s)")
            recommendation_detail = (
                f"<li>Evidence basis: "
                f"{html.escape(recommendation_lineage)}.</li>"
                f"<li>Declared action and constraint: "
                f"{html.escape(recommendation.action)}</li>"
                f"<li>Declared adjustment: {html.escape(amount)} per "
                f"{html.escape(recommendation.cadence or 'declared cadence')}."
                "</li>")
        else:
            recommendation_lineage = (
                f"Declared scenario with "
                f"{len(recommendation.assumption_references)} "
                "assumption reference(s)")
            raw_impact = (
                f"{recommendation.estimated_delta_v_days:.1f} days"
                if recommendation.estimated_delta_v_days is not None
                else "not available")
            recommendation_detail = (
                f"<li>Evidence basis: "
                f"{html.escape(recommendation_lineage)}.</li>"
                f"<li>Declared action: "
                f"{html.escape(recommendation.action)}</li>"
                f"<li>Modelled adjustment: {html.escape(amount)} per "
                f"{html.escape(recommendation.cadence or 'declared cadence')}."
                f"</li><li>Modelled ETA change: {html.escape(raw_impact)}; "
                f"displayed at month resolution.</li>")

    telemetry_cards = []
    for item in assessment.telemetry:
        result = item.result
        value = (
            _format_value(
                result.value, result.unit_or_currency, item.format_kind)
            if result.status in ("available", "stale") else result.status.upper())
        qualifier = f" · {item.qualifier}" if item.qualifier else ""
        telemetry_cards.append(
            f'<div class="telemetry"><p class="k">{html.escape(item.label)}</p>'
            f'<p class="value num">{html.escape(value)}</p>'
            f'<p class="sub">{html.escape(result.status.upper())} · '
            f'{len(result.input_references)} INPUT EVENT(S)'
            f'{html.escape(qualifier)}</p></div>')

    notes = [assessment.confidence_basis, *assessment.limitations]
    if assessment.confidence is not None:
        notes.insert(
            0,
            f"MISSION CONFIDENCE · {assessment.confidence.state.upper()} · "
            f"{assessment.confidence.basis}",
        )
    note_items = "".join(f"<li>{html.escape(note)}</li>" for note in notes if note)
    achieved_delta = (
        (
            "LESS THAN 1 MONTH GAINED"
            if delta_v.months == 0 else
            f"ABOUT {abs(delta_v.months)} MONTH"
            f"{'S' if abs(delta_v.months) != 1 else ''} GAINED"
        )
        if delta_v is not None and delta_v.months is not None
        and delta_v.direction == "accelerated" else
        _format_month_delta(
            delta_v.months if delta_v else None,
            delta_v.direction if delta_v else None)
    )
    has_reference_schedule = (
        delta_v is not None
        and delta_v.reference_start_at is not None
        and bool(delta_v.reference_start_label)
        and delta_v.reference_destination_at is not None
        and bool(delta_v.reference_destination_label)
    )
    current_label, current_format_kind = (
        _assessment_current_presentation(assessment))
    flight_analysis_schedule = f"""<div class="flight-analysis-schedule"
    aria-label="Mission schedule comparison">
    <div class="time-point"><p class="k">{html.escape(
        delta_v.reference_start_label)}</p>
      <p class="v">{html.escape(_month_year(
          delta_v.reference_start_at))}</p></div>
    <div class="time-point"><p class="k">CURRENT POSITION</p>
      <p class="v num">{html.escape(_format_value(
          assessment.current_value.value,
          assessment.current_value.unit_or_currency,
          current_format_kind))}</p></div>
    <div class="time-point"><p class="k">EXPECTED DESTINATION</p>
      <p class="v">{html.escape(_month_year(assessment.eta))}</p></div>
    <div class="time-point"><p class="k">{html.escape(
        delta_v.reference_destination_label)}</p>
      <p class="v">{html.escape(_month_year(
          delta_v.reference_destination_at))}</p>
      <p class="sub">{html.escape(achieved_delta)}</p></div>
  </div>""" if (
        has_reference_schedule
        and assessment.applicability.eta == "applicable"
    ) else ""
    schedule_summary = (
        f" Expected destination is {_month_year(assessment.eta)}; "
        f"{delta_v.reference_destination_label.lower()} is "
        f"{_month_year(delta_v.reference_destination_at)}; achieved change is "
        f"{achieved_delta}."
        if has_reference_schedule else
        f" Expected destination is {_month_year(assessment.eta)}."
    ) if assessment.applicability.eta == "applicable" else (
        " Expected destination is not available."
        if assessment.applicability.eta == "unavailable" else "")
    delta_period = (
        delta_v.period_label
        if delta_v is not None and delta_v.period_label else
        f"LAST {delta_v.lookback_days if delta_v else 0} DAYS"
    )
    eta_tile = (
        f"""<div><p class="k">ETA · {html.escape(completion_label)}</p>
        <p class="v">{html.escape(eta)}</p></div>"""
        if assessment.applicability.eta == "applicable" else
        """<div><p class="k">ETA</p>
        <p class="v">NOT AVAILABLE</p>
        <p class="sub">An arrival estimate is not available for this mission.</p></div>"""
        if assessment.applicability.eta == "unavailable" else ""
    )
    trajectory_tile = (
        f"""<div><p class="k">TRAJECTORY</p>
        <p class="v {trajectory_class}">{html.escape(trajectory_label)}</p></div>"""
        if assessment.applicability.trajectory == "applicable" else
        """<div><p class="k">TRAJECTORY</p>
        <p class="v none">NOT AVAILABLE</p>
        <p class="sub">Trajectory history is not available for this mission.</p></div>"""
        if assessment.applicability.trajectory == "unavailable" else ""
    )
    delta_instrument = (
        f"""<div class="instrument"><p class="k">Δv · {html.escape(delta_period)}</p>
      <p class="v num">{html.escape(delta_value)}</p>
      <p class="sub">{html.escape(delta_sub)}</p></div>"""
        if assessment.applicability.delta_v == "applicable" else
        """<div class="instrument"><p class="k">Δv</p>
      <p class="v num">NOT AVAILABLE</p>
      <p class="sub">Schedule change is not available for this mission.</p></div>"""
        if assessment.applicability.delta_v == "unavailable" else ""
    )
    recommendation_delta_instrument = (
        f"""<div class="instrument"><p class="k">ESTIMATED Δv</p>
      <p class="v num green">{html.escape(recommendation_impact)}</p>
      <p class="sub">Month-level model resolution</p></div>"""
        if assessment.applicability.delta_v != "not_applicable" else ""
    )
    if (
        assessment.applicability.trajectory == "applicable"
        and assessment.applicability.forecast == "applicable"
        and assessment.applicability.eta == "applicable"
    ):
        accessible_summary = f"""<p class="sr-only" id="trajectory-summary">The solid historical path reaches
    {html.escape(current_label)} {html.escape(_format_value(
        assessment.current_value.value,
        assessment.current_value.unit_or_currency,
        current_format_kind))}.
    The dashed expected forecast continues through a widening low to high sensitivity
    range toward the configured milestones.{html.escape(schedule_summary)}
    Current milestone is
    {html.escape(milestone_label)}; trajectory is
    {html.escape(trajectory_label)}.</p>"""
    else:
        summary_clauses = [
            (
                f"Current position is {current_label} "
                f"{_format_value(assessment.current_value.value, assessment.current_value.unit_or_currency, current_format_kind)}."
            ),
            f"Current milestone is {milestone_label}.",
        ]
        if assessment.applicability.trajectory == "applicable":
            summary_clauses.append(
                f"Historical trajectory is {trajectory_label}.")
        elif assessment.applicability.trajectory == "unavailable":
            summary_clauses.append(
                "Trajectory history is not available for this mission.")
        if assessment.applicability.forecast == "applicable":
            summary_clauses.append(
                "An expected low to high sensitivity forecast is shown.")
        elif assessment.applicability.forecast == "unavailable":
            summary_clauses.append(
                "Forecast evidence is not available for this mission.")
        if assessment.applicability.eta == "applicable":
            summary_clauses.append(
                f"Expected destination is {_month_year(assessment.eta)}.")
        elif assessment.applicability.eta == "unavailable":
            summary_clauses.append(
                "An arrival estimate is not available for this mission.")
        accessible_summary = (
            '<p class="sr-only" id="trajectory-summary">'
            + html.escape(" ".join(summary_clauses))
            + "</p>")
    reference_schedule_class = (
        " reference-schedule-relocated" if flight_analysis_schedule else "")
    hero = _render_mission_hero(_MissionHeroView(
        title=definition.label,
        definition=definition.definition,
        return_link=mission_return,
        sun_phase=_sun_phase(as_of),
        reference_schedule_class=reference_schedule_class,
        trajectory=_mission_trajectory_svg(assessment),
        milestone_label=milestone_label,
        trajectory_tile=trajectory_tile,
        eta_tile=eta_tile,
        margin_value=margin_value,
        margin_sub=margin_sub,
        accessible_summary=accessible_summary,
    ))
    analysis = _render_flight_analysis(_FlightAnalysisView(
        schedule=flight_analysis_schedule,
        delta_instrument=delta_instrument,
        milestone_completion=milestone_completion,
        milestone_label=milestone_label,
        recommendation_action=recommendation_action,
        recommendation_amount=recommendation_amount,
        recommendation_delta_instrument=recommendation_delta_instrument,
    ))
    mission_data = _render_mission_data(_MissionDataView(
        telemetry_cards=tuple(telemetry_cards),
        recommendation_detail=recommendation_detail,
        note_items=note_items,
        input_reference_count=len(assessment.input_references),
        assumption_reference_count=len(assessment.assumption_references),
    ))
    body = f"""{hero}
{analysis}
{mission_data}
{_footer(console)}"""
    return _render(definition.label, body, as_of, "/missions")


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
