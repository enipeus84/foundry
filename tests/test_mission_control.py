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
                 "/decisions", "/missions", "/settings"):
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
    assert 'class="card mission"' in html
    assert "Financial independence glide path" in html
    assert "TARGET £450,000" in html
    assert "TELEMETRY" in html  # the drill-down affordance


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
    assert "NET CASH FLOW" in html
    assert "SINCE FIRST OBSERVATION" in html


def test_navigation_is_hidden_by_default_and_script_free(tmp_path):
    """RFC-004 navigation: a CSS-only drawer (checkbox toggle), zero
    JavaScript anywhere on the page — the CSP has no script-src and
    nothing on the page needs one."""
    _seed(tmp_path)
    html = client().get("/").text
    assert 'id="nav-toggle"' in html
    assert 'class="drawer"' in html
    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
    for handler in ("onclick=", "onload=", "onerror=", "onfocus="):
        assert handler not in html.lower()
