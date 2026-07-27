"""Mission Control v0.1 (RFC-003): the five properties the RFC demands
proven — Core-only imports, registry-only metric access, graceful
missing metrics, intact authentication, deterministic rendering — plus
the read-only guarantee. Skips cleanly without the [web] extra."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.entities import declare_mission  # noqa: E402
from foundry.core.evidence import concern, derive_claim_directly, tag_claim  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.fixtures import build_parker_brads_household  # noqa: E402
from foundry.web import app, _build_console  # noqa: E402

ALLOWED = "cparkerbrads@gmail.com"

# Everything the Finance provider owns (registered by the composition
# root) — unchanged by RFC-004, which only changed what the opening
# screen shows.
KPI_METRIC_IDS = {
    "finance.net_worth", "finance.liquidity_runway",
    "finance.employer_concentration", "finance.debt_ratio",
    "finance.cash_available",
}

# The exactly-four opening-screen KPIs (RFC-004).
HOME_KPI_IDS = {
    "finance.net_worth", "finance.cash_available",
    "finance.cash_flow", "finance.liquidity_runway",
}


@pytest.fixture(autouse=True)
def auth_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    yield


def _seed(tmp_path) -> None:
    """The same shape examples/seed_mission_control.py writes: the
    Parker-Brads fixture, an active Mission, one recommendation."""
    log = EventLog(tmp_path / "events.jsonl")
    household = build_parker_brads_household(log)
    declare_mission(log, "Financial independence glide path",
                     target_metric="finance.net_worth",
                     target_value=450_000.0, tolerance=50_000.0)
    _, claim_id = derive_claim_directly(
        log, statement="Reduce employer concentration below 25%.",
        confidence=0.8, evidence=["concentration 32%"],
        provenance=[household.chris_id], actor="user")
    tag_claim(log, claim_id, "insight_type", "recommendation")
    concern(log, claim_id, household.household_id)


def client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
        ALLOWED, webauth.load_config()))
    return c


# ------------------------------------------------------- 1. import boundary

def test_mission_control_imports_only_core_interfaces():
    """RFC-003's architectural rule, enforced structurally: the
    surface's own source names no Finance calculation module, no model
    adapter, no Kernel — only Core contracts, the substrate's read
    types, and the auth layer."""
    import ast as ast_mod
    import inspect

    import foundry.mission_control as mc
    tree = ast_mod.parse(inspect.getsource(mc))
    imported = {alias.name for node in ast_mod.walk(tree)
                if isinstance(node, ast_mod.Import) for alias in node.names} | \
        {node.module for node in ast_mod.walk(tree)
         if isinstance(node, ast_mod.ImportFrom) and node.module}

    forbidden_prefixes = ("foundry.finance", "foundry.models", "foundry.kernel")
    assert not any(m.startswith(forbidden_prefixes) for m in imported), imported

    allowed_foundry = ("foundry.core", "foundry.canon", "foundry.eventlog",
                        "foundry.webauth", "foundry")
    for module in imported:
        if module.startswith("foundry"):
            assert module.startswith(allowed_foundry), module


def test_composition_root_not_mission_control_wires_finance():
    """The one sanctioned meeting point: web.py registers the Finance
    provider; the console handed to Mission Control already contains a
    populated registry."""
    console = _build_console()
    assert KPI_METRIC_IDS <= console.registry.owned_metric_ids()


# -------------------------------------------- 2. metrics through the registry

def test_kpis_are_obtained_through_the_metric_registry(monkeypatch, tmp_path):
    """Every card value on the opening page travelled through
    `registry.dispatch` — observed by wrapping the real registry's
    dispatch and counting what the page pulled through it."""
    _seed(tmp_path)
    dispatched: list[str] = []

    def spying_console():
        console = _build_console()
        real_dispatch = console.registry.dispatch

        def spy(request):
            dispatched.append(request.metric_id)
            return real_dispatch(request)

        console.registry.dispatch = spy
        return console

    monkeypatch.setattr(app.state, "console_factory", spying_console)
    r = client().get("/")
    assert r.status_code == 200
    assert HOME_KPI_IDS <= set(dispatched)
    # And the values on the page are the registry's, not literals:
    assert "£480,760" in r.text          # net worth, computed by Finance
    assert "£18,960" in r.text           # cash available (liquid accounts)
    # Exactly four KPI cards on the opening screen (RFC-004):
    assert r.text.count('class="card kpi"') == 4


# ------------------------------------------------ 3. missing metrics graceful

def test_missing_metrics_fail_gracefully(monkeypatch, tmp_path):
    """An empty registry — no Finance provider at all — must produce a
    calm page of UNSUPPORTED cards, never a crash or an invented
    number."""
    _seed(tmp_path)

    def finance_less_console():
        from foundry.core.metrics import MetricRegistry
        console = _build_console()
        console.registry = MetricRegistry()  # nothing registered
        return console

    monkeypatch.setattr(app.state, "console_factory", finance_less_console)
    r = client().get("/")
    assert r.status_code == 200
    assert r.text.count("UNSUPPORTED") >= 4  # all four cards, honestly
    assert "£" not in r.text                 # no fabricated value anywhere


def test_mission_without_evaluable_metric_shows_not_evaluable(monkeypatch, tmp_path):
    """A Mission that exists but cannot be evaluated must never be
    reported as 'NO ACTIVE MISSION' — the two states are different
    facts, and conflating them misleads the operator."""
    _seed(tmp_path)

    def finance_less_console():
        from foundry.core.metrics import MetricRegistry
        console = _build_console()
        console.registry = MetricRegistry()
        return console

    monkeypatch.setattr(app.state, "console_factory", finance_less_console)
    html = client().get("/").text
    assert "NOT EVALUABLE" in html
    assert "NO ACTIVE MISSION" not in html
    assert "Financial independence glide path" in html  # the mission is still named


def test_unknown_metric_drill_down_is_harmless(tmp_path):
    _seed(tmp_path)
    r = client().get("/metrics/nobody.owns_this")
    assert r.status_code == 200
    assert "UNSUPPORTED" in r.text


# --------------------------------------------------------- 4. auth unchanged

def test_authentication_still_protects_every_surface(tmp_path):
    _seed(tmp_path)
    anonymous = TestClient(app, follow_redirects=False)
    for path in ("/", "/metrics/finance.net_worth", "/finance",
                 "/decisions", "/missions",
                 "/missions/financial-independence", "/settings"):
        r = anonymous.get(path)
        assert r.status_code == 303, path
        assert r.headers["location"] == "/login", path


def test_wrong_account_session_is_rejected(tmp_path):
    _seed(tmp_path)
    c = TestClient(app, follow_redirects=False)
    c.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
        "intruder@example.com", webauth.load_config()))
    assert c.get("/").status_code == 303


# ------------------------------------------------- 5. deterministic rendering

def test_opening_page_renders_deterministically(tmp_path):
    """Two renders of the same log are byte-identical: no wall clock in
    any value (`as_of` is the latest event's timestamp), no random
    ordering anywhere."""
    _seed(tmp_path)
    c = client()
    assert c.get("/").text == c.get("/").text


def test_drill_down_renders_deterministically(tmp_path):
    _seed(tmp_path)
    c = client()
    assert c.get("/metrics/finance.net_worth").text == \
           c.get("/metrics/finance.net_worth").text


# ------------------------------------------------------------ read-only + UX

def test_mission_control_never_appends_an_event(tmp_path):
    """The whole surface is a consumer: rendering every page leaves
    the event log byte-for-byte identical."""
    _seed(tmp_path)
    log_path = tmp_path / "events.jsonl"
    before = log_path.read_bytes()
    c = client()
    for path in ("/", "/metrics/finance.net_worth", "/metrics/finance.debt_ratio",
                 "/finance", "/decisions", "/missions", "/settings"):
        assert c.get(path).status_code == 200
    assert log_path.read_bytes() == before


def test_home_shows_nominal_flight_plan_and_flight_director(tmp_path):
    """Seeded state: net worth £480,760 vs target £450k ±£50k →
    on_track → NOMINAL (RFC-004's flight vocabulary) — evaluated by
    Core, only rendered here. The recommendation Claim surfaces in the
    Flight Director panel via the Evidence Index."""
    _seed(tmp_path)
    html = client().get("/").text
    assert "NOMINAL" in html
    assert "Financial independence glide path" in html
    assert "Reduce employer concentration below 25%." in html
    assert "CONFIDENCE 80%" in html
    assert "EVIDENCE ITEMS 1" in html
    assert "EVIDENCE VERIFIED" not in html


def test_drill_down_shows_full_lineage(tmp_path):
    _seed(tmp_path)
    html = client().get("/metrics/finance.net_worth").text
    assert "RAW RESULT" in html
    assert "input_references" in html
    assert "calculation_version" in html
    assert "ATTRIBUTION" in html
    assert html.count("MEMBER") >= 4  # all four Parker-Brads members listed


# ------------------------------------------------ RFC-004: Flight Deck UI

def test_flight_deck_hero_answers_the_three_questions(tmp_path):
    """Am I on course? (FLIGHT PLAN word) · Why? (the evidence line
    naming the mission and its numbers) · Do I need to do anything?
    (the course-corrections count and the Flight Director)."""
    _seed(tmp_path)
    html = client().get("/").text
    assert "FLIGHT PLAN" in html
    assert "STRATEGIC RISK" in html
    assert "RECOMMENDED COURSE CORRECTIONS" in html
    assert "FLIGHT DIRECTOR" in html
    assert "APOLLO MISSIONS" in html
    # The "why" line carries the real numbers, not a slogan:
    assert "£480,760" in html and "£450,000" in html


def test_apollo_mission_card_shows_status_progress_and_drill_down(tmp_path):
    _seed(tmp_path)
    html = client().get("/").text
    assert 'class="card mission live"' in html
    assert "Financial independence glide path" in html
    assert "TARGET £450,000" in html
    assert 'href="/metrics/finance.net_worth"' in html


def test_apollo_programme_shows_four_honest_mission_lanes(tmp_path):
    _seed(tmp_path)
    html = client().get("/").text
    for title in ("Mortgage Freedom", "Financial Independence", "Retirement"):
        assert title in html
    assert "Children" in html and "Future" in html
    assert html.count('class="card mission live"') == 1
    assert html.count('class="card mission planned"') == 3
    assert html.count("TARGET NOT DECLARED") == 3


def test_flight_director_says_so_when_nothing_needs_doing(tmp_path):
    """RFC-004: if no action is required the interface must say so
    explicitly — seeded here without any recommendation Claim."""
    log = EventLog(tmp_path / "events.jsonl")
    build_parker_brads_household(log)
    declare_mission(log, "Financial independence glide path",
                     target_metric="finance.net_worth",
                     target_value=450_000.0, tolerance=50_000.0)
    html = client().get("/").text
    assert "Flight Plan remains nominal." in html
    assert "No intervention required." in html


def test_recent_course_corrections_surface_reviewed_decisions(tmp_path):
    """A Decision Review claim concerning the household appears in the
    Recent Course Corrections panel with its verdict."""
    from foundry.core.decisions import (
        concern_decision, declare_decision, declare_outcome, declare_review)

    log = EventLog(tmp_path / "events.jsonl")
    household = build_parker_brads_household(log)
    declare_mission(log, "Financial independence glide path",
                     target_metric="finance.net_worth",
                     target_value=450_000.0, tolerance=50_000.0)
    decision = declare_decision(log, "Raise pension contributions by 2%.")
    concern_decision(log, decision.id, household.household_id)
    outcome = declare_outcome(log, decision, observed_metric="finance.net_worth",
                               observed_value=481_000.0, observed_at=1.0)
    declare_review(log, decision, outcome,
                    statement="Pension contribution raised; trajectory improved.",
                    review_verdict="achieved", concerns=[household.household_id])

    html = client().get("/").text
    assert "RECENT COURSE CORRECTIONS" in html
    assert "Pension contribution raised; trajectory improved." in html
    assert "ACHIEVED" in html


def test_dynamic_claim_content_is_escaped(tmp_path):
    """Secure by Design: statements from the log render inert — a
    hostile claim can never become markup or script."""
    log = EventLog(tmp_path / "events.jsonl")
    household = build_parker_brads_household(log)
    _, claim_id = derive_claim_directly(
        log, statement='<script>alert("x")</script>',
        confidence=0.5, evidence=["e"], provenance=[household.chris_id], actor="user")
    tag_claim(log, claim_id, "insight_type", "recommendation")
    concern(log, claim_id, household.household_id)

    html = client().get("/").text
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# -------------------------------------- RFC-004B: information honesty

def _seed_household_with(tmp_path):
    """Bare Parker-Brads household; each test declares its own
    Missions and Claims on the returned log."""
    log = EventLog(tmp_path / "events.jsonl")
    household = build_parker_brads_household(log)
    return log, household


def test_mission_gauge_is_honest_for_lower_is_better_metrics(tmp_path):
    """Mortgage Freedom: debt ratio 30.4% against a 25% target is a
    deviation, and must render as one — a positive variance and a
    deviation gauge, never a filled 'progress' bar (the RFC-004 bar
    showed >100% completion for exactly this state)."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Mortgage Freedom", target_metric="finance.debt_ratio",
                     target_value=0.25, tolerance=0.03)
    html = client().get("/").text
    assert 'class="m-bar"' not in html          # the misleading metaphor is gone
    assert 'class="m-gauge"' in html
    assert '<span class="zone"></span>' in html  # exact-target tolerance band
    assert "+5.4% FROM TARGET" in html          # signed, in the metric's units
    assert "WATCH" in html                      # Core's verdict, unchanged


def test_mission_gauge_is_honest_for_higher_is_better_metrics(tmp_path):
    """Retirement short of target: the same gauge, deviation signed
    the other way."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Retirement", target_metric="finance.net_worth",
                     target_value=600_000.0, tolerance=70_000.0)
    html = client().get("/").text
    assert "−£119,240 FROM TARGET" in html
    assert 'class="m-gauge"' in html


def test_mission_inside_declared_range_says_within_range(tmp_path):
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Stability corridor", target_metric="finance.net_worth",
                     target_range=(400_000.0, 500_000.0), tolerance=50_000.0)
    html = client().get("/").text
    assert "WITHIN RANGE" in html
    assert "RANGE £400,000–£500,000" in html
    assert "against a target range of £400,000–£500,000." in html
    assert "against a target of —" not in html
    assert '<span class="zone"></span>' not in html


def test_range_mission_watch_gauge_has_no_false_target_band(tmp_path):
    """Outside a declared range, Core says WATCH even when the value is
    within one tolerance of the edge. The tick remains, but the target-value
    tolerance band must not imply that the WATCH state is on target."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Stability corridor", target_metric="finance.net_worth",
                     target_range=(500_000.0, 600_000.0), tolerance=50_000.0)
    html = client().get("/").text
    assert "WATCH" in html
    assert "−£19,240 OUTSIDE RANGE" in html
    assert "against a target range of £500,000–£600,000." in html
    assert 'class="m-gauge"' in html
    assert '<span class="zone"></span>' not in html


def test_mission_without_numeric_target_gets_no_gauge(tmp_path):
    """Binary/underspecified Missions: no target declared → Core
    refuses to fabricate a status and the card refuses to fabricate a
    gauge."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Household resilience")
    html = client().get("/").text
    assert "NOT EVALUABLE" in html
    assert 'class="m-gauge"' not in html


def test_flight_director_addresses_the_deviating_mission(tmp_path):
    """OFF COURSE because of Retirement → the surfaced correction is
    one whose Claim concerns that Mission, and the lede says so."""
    log, household = _seed_household_with(tmp_path)
    mission = declare_mission(log, "Retirement", target_metric="finance.net_worth",
                               target_value=750_000.0, tolerance=50_000.0)
    _, unrelated = derive_claim_directly(
        log, statement="Rebalance the ISA into the tracker fund.",
        confidence=0.7, evidence=["e"], provenance=[household.chris_id], actor="user")
    tag_claim(log, unrelated, "insight_type", "recommendation")
    concern(log, unrelated, household.household_id)
    _, related = derive_claim_directly(
        log, statement="Raise pension contributions by 3% to close the Retirement gap.",
        confidence=0.8, evidence=["e"], provenance=[household.household_id], actor="user")
    tag_claim(log, related, "insight_type", "recommendation")
    concern(log, related, mission.id)

    html = client().get("/").text
    assert "OFF COURSE" in html
    assert "Course correction for Retirement." in html
    assert "Raise pension contributions by 3%" in html
    # The unrelated recommendation must not appear under a red banner:
    assert "Rebalance the ISA into the tracker fund." not in html


def test_flight_director_admits_when_no_relevant_correction_exists(tmp_path):
    """Deviation with only unrelated recommendations on file: the panel
    states the absence rather than borrowing unrelated advice."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Retirement", target_metric="finance.net_worth",
                     target_value=750_000.0, tolerance=50_000.0)
    _, unrelated = derive_claim_directly(
        log, statement="Rebalance the ISA into the tracker fund.",
        confidence=0.7, evidence=["e"], provenance=[household.chris_id], actor="user")
    tag_claim(log, unrelated, "insight_type", "recommendation")
    concern(log, unrelated, household.household_id)

    html = client().get("/").text
    assert "No course correction on file for Retirement." in html
    assert "nothing is invented" in html
    assert "1 standing recommendation on file concern" in html
    assert "Rebalance the ISA into the tracker fund." not in html


def test_cash_flow_card_declares_its_measurement_period(tmp_path):
    """finance.cash_flow without a horizon is net flow since first
    observation; the card must say so, on the card."""
    _seed(tmp_path)
    html = client().get("/").text
    assert "CASH FLOW" in html
    assert "SINCE FIRST OBSERVATION" in html
    assert "VIEW TELEMETRY" not in html


def test_navigation_is_hidden_by_default_and_uses_no_inline_script(tmp_path):
    """RFC-004.1 navigation: a deliberately opened dialog with a clear
    close control. The small external script owns focus return, Escape,
    and trapping; no inline handlers or unsafe dynamic HTML are used."""
    _seed(tmp_path)
    html = client().get("/").text
    assert 'id="nav-open"' in html
    assert 'id="primary-drawer"' in html
    assert 'aria-modal="true"' in html
    assert 'data-nav-close' in html
    assert '<script src="/static/flight-deck.js" defer></script>' in html
    assert "JavaScript is unavailable. The navigation drawer cannot open" in html
    assert 'aria-label="Primary navigation (JavaScript unavailable)"' in html
    assert html.count('href="/finance"') == 2
    assert "javascript:" not in html.lower()
    for handler in ("onclick=", "onload=", "onerror=", "onfocus="):
        assert handler not in html.lower()


def test_earthrise_is_prioritised_local_and_accessible(tmp_path):
    _seed(tmp_path)
    html = client().get("/").text
    assert 'rel="preload" as="image" href="/static/earthrise.webp"' in html
    assert 'src="/static/earthrise.webp"' in html
    assert 'fetchpriority="high"' in html
    assert 'alt="Earth at sunrise from orbit' in html
    assert 'class="earthrise"' in html
    assert '<svg class="earthrise"' not in html


def test_scope_controls_do_not_imply_unsupported_individual_metrics(tmp_path):
    _seed(tmp_path)
    html = client().get("/").text
    assert 'aria-label="Financial scope"' in html
    assert 'HOUSEHOLD<small>ACTIVE</small>' in html
    for name in ("CHRIS", "FIONA", "HAMISH", "HARRIET"):
        assert f'disabled>{name}<small>FUTURE SCOPE</small>' in html


# ---------------------------------------- RFC-005 Financial Independence slice

def _seed_financial_independence(tmp_path):
    from foundry.demo_data import build

    log = EventLog(tmp_path / "events.jsonl")
    build(log)
    return log


def test_financial_independence_home_lane_opens_mission_detail(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/").text
    assert 'href="/missions/financial-independence"' in html
    assert "Coast FIRE by 2038" in html


def test_financial_independence_route_renders_assessment_not_calculations(tmp_path):
    _seed_financial_independence(tmp_path)
    response = client().get("/missions/financial-independence")
    assert response.status_code == 200
    html = response.text
    assert "Financial Independence" in html
    assert "Mission trajectory" in html
    assert "MISSION MARGIN" in html
    assert "Δv" in html
    assert "low to high sensitivity corridor" in html
    assert "ACCESSIBLE ASSETS" in html
    assert "Increase ISA contribution" in html
    assert "£250 per month" in html
    assert "NOT A PROBABILITY" in html
    assert "CONFIDENCE 78%" not in html
    assert "Confidence: 78%" not in html
    assert html.count('src="/static/earthrise.webp"') == 1


def test_financial_independence_trajectory_is_integrated_into_hero(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/missions/financial-independence").text
    hero_start = html.index('<section class="hero mission-detail-hero')
    hero_end = html.index("</section>", hero_start)
    hero = html[hero_start:hero_end]

    assert 'class="trajectory-svg hero-trajectory"' in hero
    assert 'class="range-envelope-aura"' in hero
    assert 'class="range-envelope-core"' in hero
    assert 'class="actual-path"' in hero
    assert 'class="forecast-path"' in hero
    assert "MISSION MARGIN" in hero
    assert "FLIGHT STATUS" in hero
    assert "ETA · INDEPENDENT" in hero
    assert "low to high sensitivity" in hero
    assert "trajectory-legend" not in hero
    assert "trajectory-shell" not in html
    assert '<h2 id="trajectory-heading">' not in html


def test_financial_independence_analysis_reduces_duplication(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/missions/financial-independence").text
    analysis_start = html.index('<section aria-labelledby="analysis-heading">')
    analysis_end = html.index("</section>", analysis_start)
    analysis = html[analysis_start:analysis_end]

    assert "Δv · LAST" in analysis
    assert "PHASE COMPLETION" in analysis
    assert "NEXT BURN" in analysis
    assert "Increase ISA contribution" in analysis
    assert "£250 per month" in analysis
    assert "ESTIMATED Δv" in analysis
    assert "Scenario " not in analysis
    assert "FLIGHT STATUS" not in analysis
    assert "ETA · INDEPENDENT" not in analysis
    assert "MISSION MARGIN" not in analysis
    assert '<details class="mission-drilldown">' in html
    assert "<summary>DEEPER MISSION DATA" in html
    drilldown = html[html.index('<details class="mission-drilldown">'):]
    assert "Next Burn source: Scenario " in drilldown
    assert "Declared action: Increase monthly ISA contribution by £250" in drilldown


def test_financial_independence_milestones_are_keyboard_and_text_accessible(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/missions/financial-independence").text

    assert html.count('class="mission-milestone ') == 4
    assert html.count('tabindex="0"') >= 5  # Today, then four milestones
    assert 'role="img"' not in html
    assert html.index('class="current-position" tabindex="0"') \
        < html.index('class="mission-milestone ')
    assert 'role="group" aria-label="Building Capital.' in html
    assert 'role="group" aria-label="Escape Velocity.' in html
    assert 'role="group" aria-label="Independent.' in html
    assert 'role="group" aria-label="Abundance.' in html
    assert "Current phase." in html
    assert "Mission completion milestone." in html
    assert "Estimated " in html
    assert 'aria-describedby="trajectory-summary"' in html
    assert ".mission-milestone:focus .milestone-detail" in html
    assert ".mission-milestone:focus-visible" in html


def test_financial_independence_uses_one_smooth_orbital_arc(tmp_path):
    import re

    _seed_financial_independence(tmp_path)
    html = client().get("/missions/financial-independence").text
    actual = re.search(r'class="actual-path" d="([^"]+)"', html)
    forecast = re.search(r'class="forecast-path" d="([^"]+)"', html)

    assert actual and forecast
    assert "Q" in actual.group(1) and "T" in actual.group(1)
    assert "Q" in forecast.group(1) and "T" in forecast.group(1)
    assert 'id="range-feather-wide"' in html
    assert 'id="range-feather-close"' in html
    assert "range-envelope-aura" in html
    assert "range-envelope-core" in html
    assert "trajectory-legend" not in html
    assert 'class="current-halo"' in html
    assert 'font-size="10.5" font-weight="700"' in html


def test_financial_independence_mobile_keeps_briefing_and_trajectory_distinct(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/missions/financial-independence").text

    assert "@media (max-width: 620px)" in html
    assert ".mission-detail-hero { min-height: 780px;" in html
    assert "height: 390px; justify-content: flex-start;" in html
    assert "inset: 350px -40px 0 -70px;" in html
    assert ".hero-trajectory .milestone-detail { opacity: 0; }" in html
    assert ".mission-milestone:focus .milestone-detail" in html


def _synthetic_assessment(forecast=(), phases=None):
    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import (
        MissionAssessment, MissionPhaseAssessment, TrajectoryPoint,
    )
    from foundry.core.scope import Subject

    scope = Subject("party", "household-test")
    phase_values = phases or (
        MissionPhaseAssessment(
            "capital", "Capital Assembly", 0.0, 400.0, .75,
            order=0, unit_or_currency="USD", is_current=True),
        MissionPhaseAssessment(
            "velocity", "Velocity Gate", 400.0, 900.0, 0.0,
            order=1, unit_or_currency="USD"),
        MissionPhaseAssessment(
            "free", "Choice Point", 900.0, 1_700.0, 0.0,
            order=2, unit_or_currency="USD", completes_mission=True),
        MissionPhaseAssessment(
            "surplus", "Surplus Orbit", 1_700.0, None, 0.0,
            order=3, unit_or_currency="USD"),
    )
    return MissionAssessment(
        mission_id="mission-test", policy_id="domain.policy.v9",
        scope=scope, as_of=4.0, status="amber",
        calculation_version="domain-calc-v9",
        current_value=MetricResult(
            metric_id="domain.capacity", value=300.0,
            unit_or_currency="USD", scope=scope, as_of=4.0,
            status="available", calculation_version="domain-v1"),
        flight_status_id="nominal", flight_status_label="Nominal",
        phase=phase_values[0], phases=phase_values,
        trajectory=(
            TrajectoryPoint(1.0, 100.0),
            TrajectoryPoint(2.0, 200.0),
            TrajectoryPoint(3.0, 300.0),
        ),
        forecast=tuple(forecast),
    )


def test_sensitivity_geometry_uses_distinct_low_and_high_paths():
    from foundry.core.mission_assessment import ForecastPoint
    from foundry.mission_control import _mission_trajectory_geometry

    assessment = _synthetic_assessment((
        ForecastPoint(5.0, 330.0, 350.0, 370.0),
        ForecastPoint(6.0, 380.0, 440.0, 500.0),
        ForecastPoint(7.0, 430.0, 550.0, 670.0),
    ))
    geometry = _mission_trajectory_geometry(assessment)

    assert geometry["range_status"] == "available"
    assert geometry["low_points"] != geometry["high_points"]
    assert all(
        low[1] > high[1]
        for low, high in zip(geometry["low_points"], geometry["high_points"]))
    for low, base, high in zip(
            geometry["low_points"], geometry["base_points"],
            geometry["high_points"]):
        assert low[1] - base[1] == pytest.approx(base[1] - high[1])
    assert geometry["range_area"] > 0
    assert geometry["range_widths"][0] \
        < geometry["range_widths"][1] \
        < geometry["range_widths"][2]


def test_identical_sensitivity_paths_collapse_without_visual_width():
    from foundry.core.mission_assessment import ForecastPoint
    from foundry.mission_control import (
        _mission_trajectory_geometry, _mission_trajectory_svg,
    )

    assessment = _synthetic_assessment((
        ForecastPoint(5.0, 350.0, 350.0, 350.0),
        ForecastPoint(6.0, 450.0, 450.0, 450.0),
    ))
    geometry = _mission_trajectory_geometry(assessment)
    rendered = _mission_trajectory_svg(assessment)

    assert geometry["range_status"] == "collapsed"
    assert geometry["range_area"] == 0
    assert geometry["range_widths"] == ()
    assert 'class="range-envelope-' not in rendered
    assert 'data-range-status="collapsed"' in rendered
    assert "no sensitivity corridor is drawn" in rendered


def test_partial_or_missing_sensitivity_data_renders_honestly():
    from foundry.core.mission_assessment import ForecastPoint
    from foundry.mission_control import (
        _mission_trajectory_geometry, _mission_trajectory_svg,
    )

    partial = _synthetic_assessment((
        ForecastPoint(5.0, 330.0, 350.0, 370.0),
        ForecastPoint(6.0, float("nan"), 440.0, 500.0),
        ForecastPoint(7.0, 430.0, 550.0, 670.0),
    ))
    missing = _synthetic_assessment(())

    partial_geometry = _mission_trajectory_geometry(partial)
    assert partial_geometry["range_status"] == "partial"
    assert partial_geometry["range_area"] > 0
    assert 'data-range-status="partial"' in _mission_trajectory_svg(partial)

    missing_geometry = _mission_trajectory_geometry(missing)
    assert missing_geometry["range_status"] == "unavailable"
    assert missing_geometry["range_area"] == 0
    assert 'class="range-envelope-' not in _mission_trajectory_svg(missing)


def test_single_forecast_point_does_not_invent_a_corridor():
    from foundry.core.mission_assessment import ForecastPoint
    from foundry.mission_control import _mission_trajectory_geometry

    geometry = _mission_trajectory_geometry(_synthetic_assessment((
        ForecastPoint(5.0, 330.0, 350.0, 370.0),
    )))
    assert geometry["range_status"] == "unavailable"
    assert geometry["range_area"] == 0
    assert geometry["range_path"] == ""


def test_milestone_policy_presentation_comes_from_assessment_contract():
    import inspect

    from foundry.mission_control import _mission_trajectory_svg
    import foundry.mission_control as mission_control

    rendered = _mission_trajectory_svg(_synthetic_assessment(()))
    assert "CAPITAL ASSEMBLY" in rendered
    assert "VELOCITY GATE" in rendered
    assert "CHOICE POINT" in rendered
    assert "SURPLUS ORBIT" in rendered
    assert "BELOW $400" in rendered
    assert "$400 – $900" in rendered
    assert "ABOVE $1,700" in rendered
    assert "domain.policy.v9" not in rendered

    source = inspect.getsource(mission_control)
    for forbidden in (
        "finance.financial_independence.v1",
        "Building Capital", "Escape Velocity", "Abundance",
        "450_000", "750_000", "1_500_000",
    ):
        assert forbidden not in source


def _replace_demo_scenario(log, *, name, amount, structured=True,
                           unit_or_currency="GBP"):
    from foundry.finance import entities as finance
    from foundry.finance.entities import FinanceEntityProjection

    projection = FinanceEntityProjection(log)
    original = next(
        scenario for scenario in projection.scenarios.values()
        if scenario.status == "active")
    finance.archive_scenario(log, original.id, "test replacement")
    kwargs = {}
    if structured:
        kwargs = {
            "action_type": "increase_contribution",
            "action_label": "Increase ISA contribution",
            "unit_or_currency": unit_or_currency,
            "cadence": "month",
        }
    finance.declare_scenario(
        log, name, original.assumption_set_id,
        {"monthly_contribution_delta": amount}, **kwargs)


def test_recommendation_display_uses_structured_adjustment_not_scenario_name(tmp_path):
    log = _seed_financial_independence(tmp_path)
    _replace_demo_scenario(
        log, name="Misleading prose claims £999 weekly", amount=375.0)

    html = client().get("/missions/financial-independence").text
    analysis = html[
        html.index('<section aria-labelledby="analysis-heading">'):
        html.index("</section>", html.index(
            '<section aria-labelledby="analysis-heading">'))
    ]
    assert "Increase ISA contribution" in analysis
    assert "£375 per month" in analysis
    assert "£999" not in analysis


def test_user_controlled_scenario_name_is_escaped_in_drilldown(tmp_path):
    log = _seed_financial_independence(tmp_path)
    _replace_demo_scenario(
        log, name="<script>alert('financial-data')</script>", amount=375.0)

    html = client().get("/missions/financial-independence").text
    assert "<script>alert('financial-data')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;financial-data&#x27;)&lt;/script&gt;" in html


def test_missing_structured_recommendation_data_fails_honestly(tmp_path):
    log = _seed_financial_independence(tmp_path)
    _replace_demo_scenario(
        log, name="Increase ISA by £999", amount=275.0, structured=False)

    html = client().get("/missions/financial-independence").text
    analysis = html[
        html.index('<section aria-labelledby="analysis-heading">'):
        html.index("</section>", html.index(
            '<section aria-labelledby="analysis-heading">'))
    ]
    assert "Recommendation unavailable" in analysis
    assert "Structured Scenario data is incomplete" in analysis
    assert "£275" not in analysis
    assert "£999" not in analysis


def test_non_gbp_structured_values_are_formatted_without_rewriting():
    from foundry.mission_control import _format_value

    assert _format_value(250.0, "USD", "currency") == "$250"
    assert _format_value(250.0, "EUR", "currency") == "€250"


def test_financial_independence_home_and_detail_use_same_status_vocabulary(tmp_path):
    _seed_financial_independence(tmp_path)
    home = client().get("/").text
    card_start = home.index(
        '<a class="card mission live" href="/missions/financial-independence">')
    card_end = home.index("</a>", card_start)
    card = home[card_start:card_end]

    assert "CURRENT PHASE BUILDING CAPITAL" in card
    assert "FLIGHT STATUS · AHEAD" in card
    assert "MISSION MARGIN +" in card
    assert "FROM TARGET" not in card
    assert "TARGET £" not in card

    detail = client().get("/missions/financial-independence").text
    assert "<p class=\"k\">CURRENT PHASE</p>" in detail
    assert "<p class=\"k\">FLIGHT STATUS</p>" in detail
    assert "MISSION MARGIN" in detail
    assert "% above required pace" in detail


@pytest.mark.parametrize("months,direction,expected", [
    (0, "accelerated", "LESS THAN 1 MONTH ACCELERATED"),
    (1, "accelerated", "ABOUT 1 MONTH ACCELERATED"),
    (3, "accelerated", "ABOUT 3 MONTHS ACCELERATED"),
    (-2, "delayed", "ABOUT 2 MONTHS DELAYED"),
    (None, None, "NOT AVAILABLE"),
])
def test_month_level_delta_formatting(months, direction, expected):
    from foundry.mission_control import _format_month_delta

    assert _format_month_delta(months, direction) == expected


def test_financial_independence_route_is_deterministic_and_read_only(tmp_path):
    log = _seed_financial_independence(tmp_path)
    path = tmp_path / "events.jsonl"
    before = path.read_bytes()
    first = client().get("/missions/financial-independence").text
    second = client().get("/missions/financial-independence").text
    assert first == second
    assert path.read_bytes() == before
    assert log.verify()


def test_financial_independence_without_policy_fails_honestly(tmp_path):
    _seed(tmp_path)  # legacy scalar Mission only
    html = client().get("/missions/financial-independence").text
    assert "No active Financial Independence Mission is declared." in html
    assert "will not invent policy" in html
