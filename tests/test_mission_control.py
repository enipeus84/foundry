"""Mission Control v0.1 (RFC-003): the five properties the RFC demands
proven — Core-only imports, registry-only metric access, graceful
missing metrics, intact authentication, deterministic rendering — plus
the read-only guarantee. Skips cleanly without the [web] extra."""

import hashlib
from itertools import count
import re

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.entities import abandon_mission, declare_mission  # noqa: E402
from foundry.core.evidence import concern, derive_claim_directly, tag_claim  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.fixtures import build_parker_brads_household  # noqa: E402
from foundry.web import app, _build_console  # noqa: E402

ALLOWED = "cparkerbrads@gmail.com"
MISSION_CONTROL_FIXTURE_AS_OF = 1_785_170_000.0  # 2026-07-27T16:33:20Z

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
    event_clock = count(MISSION_CONTROL_FIXTURE_AS_OF, step=0.001)
    monkeypatch.setattr(
        "foundry.eventlog.time.time", event_clock.__next__)
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
                 "/missions/financial-independence",
                 "/missions/mortgage-freedom",
                 "/missions/financial-resilience",
                 "/missions/pension-independence",
                 "/missions/not-a-definition", "/settings"):
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




def test_drill_down_shows_full_lineage(tmp_path):
    _seed(tmp_path)
    html = client().get("/metrics/finance.net_worth").text
    assert "RAW RESULT" in html
    assert "input_references" in html
    assert "calculation_version" in html
    assert "ATTRIBUTION" in html
    assert html.count("MEMBER") >= 4  # all four Parker-Brads members listed


# ------------------------------------------------ RFC-004: Flight Deck UI





def test_apollo_programme_shows_four_honest_mission_lanes(tmp_path):
    _seed(tmp_path)
    html = client().get("/").text
    for title in (
        "Financial Resilience",
        "Financial Independence",
        "Pension Independence",
        "Mortgage Freedom",
    ):
        assert title in html
    assert "Children" not in html
    assert html.count('class="card mission live"') == 1
    assert html.count('class="card mission planned"') == 4
    assert html.count("TARGET NOT DECLARED") == 4


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










def test_mission_without_numeric_target_gets_no_gauge(tmp_path):
    """Binary/underspecified Missions: no target declared → Core
    refuses to fabricate a status and the card refuses to fabricate a
    gauge."""
    log, household = _seed_household_with(tmp_path)
    declare_mission(log, "Household resilience")
    html = client().get("/").text
    assert "NOT EVALUABLE" in html
    assert 'class="m-gauge"' not in html






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
    # Route goldens must never inherit wall-clock time: event timestamps
    # become Mission Control's as_of and can move calendar projections.
    build(log, as_of=MISSION_CONTROL_FIXTURE_AS_OF)
    return log


def test_financial_independence_home_lane_opens_mission_detail(tmp_path):
    _seed_financial_independence(tmp_path)
    html = client().get("/").text
    assert '<section id="missions">' in html
    assert 'href="/missions/financial-independence"' in html
    assert "Financial Independence" in html
    assert 'href="/missions/mortgage-freedom"' in html
    assert 'href="/missions/pension-independence"' in html
    assert "Assessment and target are planned." not in html
    assert "Pension Independence" in html
    assert ">FINANCE.MORTGAGE_BALANCE " not in html
    assert "finance.mortgage_balance 242" not in html
    assert "MORTGAGE BALANCE £242,540" in html
    assert "CURRENT POSITION · MORTGAGE BALANCE £242,540" not in html


def test_financial_independence_route_renders_assessment_not_calculations(tmp_path):
    _seed_financial_independence(tmp_path)
    response = client().get("/missions/financial-independence")
    assert response.status_code == 200
    html = response.text
    assert "Financial Independence" in html
    assert "Mission trajectory" in html
    assert "SCHEDULE BUFFER" in html
    assert "RECENT MOVEMENT" in html
    assert 'class="mission-time-lane"' not in html
    assert 'class="flight-analysis-schedule"' not in html
    assert "low to high sensitivity corridor" in html
    assert "ACCESSIBLE ASSETS" in html
    assert "Increase ISA contribution" in html
    assert "£250 per month" in html
    assert "NOT A PROBABILITY" in html
    assert "CONFIDENCE 78%" not in html
    assert "Confidence: 78%" not in html
    assert 'class="mission-return" href="/#missions"' in html
    assert html.count('src="/static/earthrise.webp"') == 1




def test_mortgage_freedom_route_renders_deterministically(tmp_path):
    _seed_financial_independence(tmp_path)
    c = client()

    assert c.get("/missions/mortgage-freedom").text == \
        c.get("/missions/mortgage-freedom").text




def test_financial_resilience_route_is_deterministic_and_read_only(tmp_path):
    log = _seed_financial_independence(tmp_path)
    before = (tmp_path / "events.jsonl").read_bytes()
    c = client()

    first = c.get("/missions/financial-resilience").text
    second = c.get("/missions/financial-resilience").text

    assert first == second
    assert (tmp_path / "events.jsonl").read_bytes() == before


def test_financial_resilience_home_lane_uses_months_without_currency(tmp_path):
    _seed_financial_independence(tmp_path)

    home = client().get("/").text
    start = home.index(
        '<a class="card mission live" '
        'href="/missions/financial-resilience">')
    end = home.index("</a>", start)
    lane = home[start:end]

    assert "CURRENT MILESTONE FORTIFIED" in lane
    assert "RESERVE COVERAGE " in lane
    assert " mo" in lane
    assert "MISSION MARGIN HIGH MARGIN" in lane
    assert "£30" not in lane
    assert "NOT IN HORIZON" not in lane


def test_month_milestone_ranges_never_render_as_currency():
    from foundry.core.mission_assessment import MissionMilestone
    from foundry.mission_control import _milestone_range_text

    buffered = MissionMilestone(
        "buffered", "Buffered", 3.0, 6.0, .5,
        unit_or_currency="months")
    fortified = MissionMilestone(
        "fortified", "Fortified", 18.0, None, 1.0,
        unit_or_currency="months")

    assert _milestone_range_text(buffered) == "3.0 mo – 6.0 mo"
    assert _milestone_range_text(fortified) == "ABOVE 18.0 mo"
    assert "£" not in _milestone_range_text(buffered)


def test_hostile_resilience_description_is_escaped_on_render(tmp_path):
    from foundry.mission_control import _as_of
    from foundry.finance.resilience_evidence import (
        record_resilience_evidence,
    )

    log = _seed_financial_independence(tmp_path)
    console = _build_console()
    household_id = next(
        party for party in console.entities.parties.values()
        if party.party_type == "household").id
    as_of = _as_of(console)
    record_resilience_evidence(
        log,
        household_id,
        "near_term_commitment",
        100.0,
        as_of,
        confidence=.9,
        source="<img src=x onerror=alert(1)>",
        lineage="<script>alert('lineage')</script>",
        unit_or_currency="GBP",
        due_at=as_of + 86_400.0,
        description="<script>alert('commitment')</script>",
    )

    html = client().get("/missions/financial-resilience").text

    assert "<script>alert('commitment')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;commitment&#x27;)&lt;/script&gt;" \
        in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "<script>alert('lineage')</script>" not in html
    assert "onerror=" not in html.lower()


def test_shipped_assessors_default_every_instrument_to_applicable(tmp_path):
    from foundry.core.mission_assessment import (
        InstrumentApplicability, MissionAssessmentRequest,
    )
    from foundry.mission_control import (
        _active_missions, _as_of, _household_scope,
    )
    from foundry.finance.mission_assessment import POLICY_ID as FI_POLICY_ID
    from foundry.finance.mortgage_assessment import (
        POLICY_ID as MORTGAGE_POLICY_ID,
    )

    _seed_financial_independence(tmp_path)
    console = _build_console()
    scope = _household_scope(console)
    as_of = _as_of(console)
    assessed = [
        console.assessments.dispatch(MissionAssessmentRequest(
            mission.id,
            mission.assessment_policy_id,
            scope,
            as_of,
        ))
        for mission in _active_missions(console)
        if mission.assessment_policy_id in {
            FI_POLICY_ID, MORTGAGE_POLICY_ID,
        }
    ]

    assert len(assessed) == 2
    assert all(
        assessment.applicability == InstrumentApplicability()
        for assessment in assessed
    )


def test_malformed_mortgage_provider_does_not_degrade_fi(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import MissionAssessmentRegistry
    from foundry.finance.mission_assessment import (
        FinancialIndependenceAssessor, POLICY_ID as FI_POLICY_ID)
    from foundry.finance.missions import register_finance_mission_definitions
    from foundry.finance.mortgage_assessment import (
        POLICY_ID as MORTGAGE_POLICY_ID)

    _seed_financial_independence(tmp_path)

    class BrokenMortgageProvider:
        def owned_policy_ids(self):
            return frozenset({MORTGAGE_POLICY_ID})

        def assess(self, request):
            raise ValueError("mortgage-private failure")

    def broken_console():
        console = _build_console()
        assessments = MissionAssessmentRegistry()
        register_finance_mission_definitions(assessments)
        assessments.register(FinancialIndependenceAssessor(
            console.registry.provider_for("finance.net_worth").finance,
            console.entities, console.registry))
        assessments.register(BrokenMortgageProvider())
        assert FI_POLICY_ID in assessments.owned_policy_ids()
        console.assessments = assessments
        return console

    monkeypatch.setattr(app.state, "console_factory", broken_console)

    failed = client().get("/missions/mortgage-freedom")
    unaffected = client().get("/missions/financial-independence")

    assert "NOT EVALUABLE" in failed.text
    assert "assessment provider failed safely" in failed.text
    assert "mortgage-private failure" not in failed.text
    assert "Mission trajectory" in unaffected.text
    assert "NOT EVALUABLE" not in unaffected.text


def test_pension_independence_route_renders_approved_policy(tmp_path):
    _seed_financial_independence(tmp_path)

    response = client().get("/missions/pension-independence")

    assert response.status_code == 200
    assert "Pension Independence" in response.text
    assert "PLANNED" not in response.text
    assert "CURRENT PENSION" in response.text
    assert "£62,000" in response.text
    assert "EXPECTED PATH" in response.text
    assert "CONSERVATIVE CASE" in response.text
    assert "OPTIMISTIC CASE" in response.text
    assert "£785,000" in response.text
    assert "EXPECTED PATH · DEFAULT VIEW · NOT A GUARANTEE" in response.text
    assert "STATE PENSION · PER YEAR" in response.text
    assert "£10,600" in response.text
    assert "ESTIMATED RETIREMENT INCOME" in response.text
    assert "£42,000" in response.text
    assert "Declared scenario increases pension contributions" in response.text
    assert "not regulated financial advice" in response.text
    assert "INCOME GAP" in response.text
    assert "NOMINAL TRAJECTORY" in response.text
    assert "NOT EVALUABLE" not in response.text
    assert "finance.pension_" not in response.text
    assert "required_retirement_income_annual" not in response.text
    assert "success probability" not in response.text.lower()
    assert "chance of success" not in response.text.lower()
    assert re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        response.text,
    ) is None
    assert 'class="mission-return" href="/#missions"' in response.text


def _render_shape_neutral_mission(
    monkeypatch,
    tmp_path,
    applicability,
    telemetry_factory=None,
    trajectory_state="Nominal",
    trajectory_movement="unknown",
):
    """Render one Core-only mock provider through the generic detail route."""
    from foundry.core.entities import declare_party
    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import (
        DeltaV, ForecastPoint, MissionAssessment, MissionAssessmentRegistry,
        MissionDefinition, MissionMargin, MissionMilestone, TrajectoryPoint,
    )

    policy_id = "domain.shape-neutral.v1"
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    log = EventLog(tmp_path / "events.jsonl")
    declare_party(log, "household")
    declare_mission(
        log,
        "Shape-neutral mission",
        assessment_policy_id=policy_id,
    )

    class ShapeNeutralProvider:
        def owned_policy_ids(self):
            return frozenset({policy_id})

        def assess(self, request):
            milestone = MissionMilestone(
                "operating", "Operating", 0.0, 10.0, .6,
                unit_or_currency="months", is_current=True,
                completes_mission=True, destination_value=10.0,
            )
            return MissionAssessment(
                mission_id=request.mission_id,
                policy_id=request.policy_id,
                scope=request.scope,
                as_of=request.as_of,
                status="green",
                calculation_version="shape-neutral-v1",
                current_value=MetricResult(
                    "domain.operating_capacity", 6.0, "months",
                    request.scope, request.as_of, "available",
                    "shape-neutral-v1",
                ),
                trajectory_state=trajectory_state,
                trajectory_tone="green",
                trajectory_movement=trajectory_movement,
                current_milestone=milestone,
                milestones=(milestone,),
                eta=(
                    request.as_of + 2_592_000.0
                    if applicability.eta == "applicable" else None
                ),
                delta_v=(
                    DeltaV(
                        30.0, 30, "one month ahead",
                        months=1, direction="accelerated",
                    )
                    if applicability.delta_v == "applicable" else None
                ),
                trajectory=(
                    (
                        TrajectoryPoint(request.as_of - 1.0, 5.0),
                        TrajectoryPoint(request.as_of, 6.0),
                    )
                    if applicability.trajectory == "applicable" else ()
                ),
                forecast=(
                    (
                        ForecastPoint(
                            request.as_of + 1.0, 6.5, 7.0, 7.5),
                        ForecastPoint(
                            request.as_of + 2.0, 7.0, 8.0, 9.0),
                    )
                    if applicability.forecast == "applicable" else ()
                ),
                telemetry=(
                    telemetry_factory(request)
                    if telemetry_factory is not None else ()
                ),
                mission_margin=(
                    MissionMargin(
                        None, None, "four months of operating tolerance",
                        "Adequate Margin", value=4.0,
                        unit_or_currency="months", format_kind="months",
                    )
                    if applicability.margin == "applicable" else None
                ),
                applicability=applicability,
            )

    def shape_neutral_console():
        console = _build_console()
        assessments = MissionAssessmentRegistry()
        assessments.register_definition(MissionDefinition(
            slug="shape-neutral",
            label="Shape Neutral",
            order=0,
            destination_direction="higher_is_better",
            definition="Maintain an honestly represented operating state.",
            assessment_policy_id=policy_id,
        ))
        assessments.register(ShapeNeutralProvider())
        console.assessments = assessments
        return console

    monkeypatch.setattr(app.state, "console_factory", shape_neutral_console)
    response = client().get("/missions/shape-neutral")
    assert response.status_code == 200
    assert 'class="mission-empty-state"' not in response.text
    return response.text


def _mission_detail_regions(rendered):
    hero_start = rendered.index('<section class="hero mission-detail-hero')
    hero_end = rendered.index("</section>", hero_start)
    analysis_start = rendered.index(
        '<section data-console-region="flight-analysis"')
    analysis_end = rendered.index("</section>", analysis_start)
    summary_start = rendered.index(
        '<p class="sr-only" id="mission-console-summary">', hero_start)
    summary_end = rendered.index("</p>", summary_start)
    return (
        rendered[hero_start:hero_end],
        rendered[analysis_start:analysis_end],
        rendered[summary_start:summary_end],
    )


def _normalized_render_hash(rendered):
    """Pin product output, excluding only volatile operational metadata."""
    normalized = re.sub(
        r"DATA AS OF [^<]+",
        "DATA AS OF <NORMALIZED> ",
        rendered,
    )
    normalized = re.sub(
        r"<footer>.*?</footer>",
        "<footer><NORMALIZED></footer>",
        normalized,
        flags=re.DOTALL,
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def test_rfc010_phase_2_route_goldens_are_pinned_for_all_four_missions(
        tmp_path):
    _seed_financial_independence(tmp_path)
    c = client()

    hashes = {
        slug: _normalized_render_hash(c.get(f"/missions/{slug}").text)
        for slug in (
            "financial-resilience",
            "financial-independence",
            "pension-independence",
            "mortgage-freedom",
        )
    }

    assert hashes == {
        "financial-resilience":
            "c82de9f26f914e9bd358b0ed620ae698fa2eb754b3fe6a39370f8f3364a24be9",
        "financial-independence":
            "0b818e93e043f86a56a00c83d224dddeacac390f42569507b7a19e02a75439e9",
        "pension-independence":
            "b683086d31525dfbd958a4ece3e84e6adaae9c3dcd1c7598bcdcc9e07cb45caf",
        "mortgage-freedom":
            "a49c9f45d10a9fcbe2cdbc949ab6f4a1d3fef86cd17e5307535dc4398b59e938",
    }


def test_route_goldens_ignore_two_distinct_frozen_wall_clocks(
        monkeypatch, tmp_path):
    _seed_financial_independence(tmp_path)
    slugs = (
        "financial-resilience",
        "financial-independence",
        "pension-independence",
        "mortgage-freedom",
    )
    rendered_at = []

    for frozen_clock in (1_609_459_200.0, 2_051_222_400.0):
        monkeypatch.setattr(
            "foundry.eventlog.time.time", lambda: frozen_clock)
        c = client()
        rendered_at.append({
            slug: _normalized_render_hash(c.get(f"/missions/{slug}").text)
            for slug in slugs
        })

    assert rendered_at[0] == rendered_at[1]




def test_d13_resilience_detail_and_home_agree_without_inventing_history(
        tmp_path):
    _seed_financial_independence(tmp_path)
    c = client()

    home = c.get("/").text
    detail = c.get("/missions/financial-resilience").text
    hero, analysis, summary = _mission_detail_regions(detail)

    assert "TRAJECTORY · COMPLETE" in home
    assert '<p class="v green">COMPLETE TRAJECTORY</p>' in hero
    assert "Trajectory unavailable" in hero
    assert "Observed trajectory history is unavailable." in analysis
    assert "Complete trajectory" in summary
    assert 'class="trajectory-svg hero-trajectory"' not in hero


def test_d13_unavailable_history_without_a_state_keeps_not_available_tile(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    rendered = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path,
        InstrumentApplicability(trajectory="unavailable"),
        trajectory_state=None,
    )
    hero, analysis, _ = _mission_detail_regions(rendered)

    assert "TRAJECTORY NOT EVALUABLE" in hero
    assert "Observed trajectory history is unavailable." in analysis






@pytest.mark.parametrize("slug,essential_count", (
    ("financial-resilience", 2),
    ("financial-independence", 2),
    ("pension-independence", 3),
    ("mortgage-freedom", 2),
))
def test_all_finance_missions_use_five_ordered_console_regions(
        tmp_path, slug, essential_count):
    _seed_financial_independence(tmp_path)

    rendered = client().get(f"/missions/{slug}").text
    regions = (
        "mission-hero",
        "flight-analysis",
        "essential-telemetry",
        "next-burn",
        "progressive-disclosure",
    )

    positions = [
        rendered.index(f'data-console-region="{region}"')
        for region in regions
    ]
    assert positions == sorted(positions)
    assert rendered.count('data-console-region="') == 5
    essential_start = rendered.index(
        'data-console-region="essential-telemetry"')
    essential_end = rendered.index("</section>", essential_start)
    essential = rendered[essential_start:essential_end]
    assert essential.count('class="telemetry"') == essential_count
    assert '<details class="mission-drilldown">' not in rendered
    assert '<details id="supporting-telemetry-1">' in rendered
    assert 'id="evidence-and-provenance"' in rendered
    assert 'id="mission-definition"' in rendered
    disclosure = rendered[rendered.index(
        'data-console-region="progressive-disclosure"'):]
    assert "aria-expanded=" not in disclosure
    assert re.search(r"<details\b[^>]*\sopen(?:\s|>)", disclosure) is None
    assert rendered.count('data-console-region="next-burn"') == 1
    assert rendered.count('class="next-burn-panel"') == 1


@pytest.mark.parametrize("slug,expected", (
    ("financial-resilience", "UNKNOWN"),
    ("financial-independence", "ADVANCING"),
    ("pension-independence", "UNKNOWN"),
    ("mortgage-freedom", "ADVANCING"),
))
def test_provider_declared_movement_reaches_shared_renderer(
        tmp_path, slug, expected):
    _seed_financial_independence(tmp_path)

    rendered = client().get(f"/missions/{slug}").text

    assert f"Movement {expected}" in rendered


def test_receding_movement_renders_without_mission_identity_branch(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    rendered = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path,
        InstrumentApplicability(),
        trajectory_movement="receding",
    )

    assert "Movement RECEDING" in rendered


def test_financial_resilience_is_the_honest_absence_path(tmp_path):
    _seed_financial_independence(tmp_path)

    rendered = client().get("/missions/financial-resilience").text
    hero, analysis, _ = _mission_detail_regions(rendered)

    assert 'class="trajectory-svg hero-trajectory"' not in hero
    assert "Trajectory unavailable" in hero
    assert "Observed trajectory history is unavailable." in analysis
    assert "RECENT MOVEMENT" not in analysis
    assert "EXPECTED INTERCEPT" not in analysis
    assert analysis.count('class="instrument"') == 1
    assert "MILESTONE COMPLETION" in analysis
    assert "Movement UNKNOWN" in hero
    assert "RECEDING" not in hero
    assert "Maintain reserve contribution" in rendered


def test_mortgage_secondary_analysis_stays_behind_disclosure(tmp_path):
    _seed_financial_independence(tmp_path)

    rendered = client().get("/missions/mortgage-freedom").text
    essential_start = rendered.index(
        'data-console-region="essential-telemetry"')
    essential_end = rendered.index("</section>", essential_start)
    essential = rendered[essential_start:essential_end]
    disclosure = rendered[rendered.index(
        'data-console-region="progressive-disclosure"'):]

    assert "MONTHLY PAYMENT" in essential
    assert "FIXED-RATE PROTECTION" in essential
    for supporting in (
        "PROPERTY ACQUISITION",
        "CURRENT EQUITY",
        "CURRENT LTV",
        "PRINCIPAL REPAID",
        "VALUATION MOVEMENT",
    ):
        assert supporting not in essential
        assert supporting in disclosure


def test_console_grids_collapse_to_real_items_without_placeholders(tmp_path):
    _seed_financial_independence(tmp_path)

    rendered = client().get("/missions/pension-independence").text
    grids = re.findall(
        r'<div class="(?:essential-grid|telemetry-grid)">(.*?)</div>\s*</div>',
        rendered,
        flags=re.DOTALL,
    )

    assert grids
    assert all('class="telemetry"' in grid for grid in grids)
    assert "repeat(auto-fit, minmax(220px,1fr))" in rendered
    assert 'class="telemetry"></div>' not in rendered


def test_zero_w_star_route_has_no_negative_or_fabricated_milestone_bands(
        tmp_path):
    from foundry.core.entities import EntityProjection
    from foundry.finance import entities as finance_entities
    from foundry.finance.entities import FinanceEntityProjection
    from foundry.finance.pension_assessment import POLICY_ID

    log = _seed_financial_independence(tmp_path)
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    existing = next(
        mission for mission in core.missions.values()
        if mission.assessment_policy_id == POLICY_ID
    )
    original = finance.assumption_sets[existing.assumption_set_id]
    assumptions = finance_entities.declare_assumption_set(
        log,
        "Pension zero-target route regression",
        "pension-zero-target-v1",
        {
            **original.assumptions,
            "required_retirement_income_annual": 10_000.0,
        },
    )
    abandon_mission(log, existing.id, "replace with zero-target regression")
    declare_mission(
        log,
        "Pension secured-income zero case",
        target_metric="finance.pension_wealth",
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id,
    )

    response = client().get("/missions/pension-independence")

    assert response.status_code == 200
    assert "REQUIRED RETIREMENT WEALTH" in response.text
    assert "W* · DECLARED INCOME NEED AND WITHDRAWAL BASIS" in response.text
    assert "£0" in response.text
    assert "£-0" not in response.text
    assert "PENSION INDEPENDENT" in response.text
    for fabricated_label in (
        "DEPENDENT",
        "FOUNDATION",
        "BUILDING",
        "APPROACHING",
    ):
        assert f">{fabricated_label}</text>" not in response.text








def test_not_applicable_instruments_are_omitted_visually_and_accessibly(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    rendered = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path,
        InstrumentApplicability(
            eta="not_applicable",
            delta_v="not_applicable",
            trajectory="not_applicable",
            forecast="not_applicable",
        ),
        trajectory_state=None,
    )
    hero, analysis, summary = _mission_detail_regions(rendered)

    assert '<p class="k">ETA' not in hero
    assert '<p class="k">TRAJECTORY</p>' in hero
    assert "TRAJECTORY NOT EVALUABLE" in hero
    assert 'class="trajectory-svg hero-trajectory"' not in hero
    assert "Trajectory unavailable" not in hero
    assert "NOT IN HORIZON" not in hero
    assert "Δv" not in analysis
    assert "solid historical path" not in summary
    assert "Trajectory not evaluable" in summary
    assert "forecast" not in summary.lower()
    assert "Destination is Operating" in summary


def test_unavailable_instruments_render_deterministic_absence_explanations(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    rendered = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path,
        InstrumentApplicability(
            eta="unavailable",
            delta_v="unavailable",
            trajectory="unavailable",
            forecast="unavailable",
        ),
    )
    hero, analysis, summary = _mission_detail_regions(rendered)

    assert "NOMINAL TRAJECTORY" in hero
    assert "Recent movement is unavailable." in analysis
    assert "NOT AVAILABLE" in analysis
    assert "Observed trajectory history is unavailable." in analysis
    assert "Forecast evidence is unavailable." in analysis
    assert "Nominal trajectory" in summary
    assert "solid historical path" not in summary
    assert "dashed expected forecast" not in summary
    assert "widening low to high sensitivity range" not in summary


def test_unavailable_and_not_applicable_trajectory_render_differently(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    unavailable = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path / "unavailable",
        InstrumentApplicability(
            eta="not_applicable",
            delta_v="not_applicable",
            trajectory="unavailable",
            forecast="not_applicable",
        ),
    )
    not_applicable = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path / "not-applicable",
        InstrumentApplicability(
            eta="not_applicable",
            delta_v="not_applicable",
            trajectory="not_applicable",
            forecast="not_applicable",
        ),
    )

    unavailable_hero, unavailable_analysis, unavailable_summary = _mission_detail_regions(
        unavailable)
    omitted_hero, omitted_analysis, omitted_summary = _mission_detail_regions(
        not_applicable)
    assert "NOMINAL TRAJECTORY" in unavailable_hero
    assert "Observed trajectory history is unavailable." in unavailable_analysis
    assert "Observed trajectory history does not apply." in omitted_analysis
    assert "NOMINAL TRAJECTORY" in omitted_hero
    assert unavailable_summary == omitted_summary


def test_forecast_prose_follows_declared_applicability(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import InstrumentApplicability

    rendered = _render_shape_neutral_mission(
        monkeypatch,
        tmp_path,
        InstrumentApplicability(forecast="not_applicable"),
    )
    hero, _, summary = _mission_detail_regions(rendered)

    assert 'class="actual-path"' in hero
    assert 'class="forecast-path"' not in hero
    assert "forecast" not in summary.lower()
    assert "Nominal trajectory" in summary




def test_unknown_generic_mission_route_fails_safely_without_reflection(tmp_path):
    _seed_financial_independence(tmp_path)

    response = client().get("/missions/%3Cscript%3E")

    assert response.status_code == 404
    assert "MISSION NOT FOUND" in response.text
    assert "<script>" not in response.text


def test_malformed_provider_degrades_only_its_defined_mission(
        monkeypatch, tmp_path):
    from foundry.core.mission_assessment import MissionAssessmentRegistry
    from foundry.finance.mission_assessment import POLICY_ID
    from foundry.finance.missions import register_finance_mission_definitions

    _seed_financial_independence(tmp_path)

    class BrokenProvider:
        def owned_policy_ids(self):
            return frozenset({POLICY_ID})

        def assess(self, request):
            raise ValueError("provider-private failure")

    def broken_console():
        console = _build_console()
        assessments = MissionAssessmentRegistry()
        register_finance_mission_definitions(assessments)
        assessments.register(BrokenProvider())
        console.assessments = assessments
        return console

    monkeypatch.setattr(app.state, "console_factory", broken_console)

    failed = client().get("/missions/financial-independence")
    unaffected = client().get("/missions/pension-independence")

    assert failed.status_code == 200
    assert "NOT EVALUABLE" in failed.text
    assert "assessment provider failed safely" in failed.text
    assert "provider-private failure" not in failed.text
    assert unaffected.status_code == 200
    assert "NOT EVALUABLE" in unaffected.text
    assert "no provider registered for this assessment policy" \
        in unaffected.text


def test_malformed_nested_provider_data_cannot_break_shared_rendering(
        monkeypatch, tmp_path):
    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import (
        MissionAssessment, MissionAssessmentRegistry)
    from foundry.finance.mission_assessment import POLICY_ID
    from foundry.finance.missions import register_finance_mission_definitions

    _seed_financial_independence(tmp_path)

    class MalformedNestedProvider:
        def owned_policy_ids(self):
            return frozenset({POLICY_ID})

        def assess(self, request):
            return MissionAssessment(
                mission_id=request.mission_id,
                policy_id=request.policy_id,
                scope=request.scope,
                as_of=request.as_of,
                status="green",
                calculation_version="malformed-v1",
                current_value=MetricResult(
                    "finance.accessible_assets", None, "GBP",
                    request.scope, request.as_of, "available",
                    "malformed-v1"),
            )

    def malformed_console():
        console = _build_console()
        assessments = MissionAssessmentRegistry()
        register_finance_mission_definitions(assessments)
        assessments.register(MalformedNestedProvider())
        console.assessments = assessments
        return console

    monkeypatch.setattr(app.state, "console_factory", malformed_console)

    home = client().get("/")
    failed = client().get("/missions/financial-independence")
    unaffected = client().get("/missions/pension-independence")

    assert home.status_code == 200
    assert failed.status_code == 200
    assert "NOT EVALUABLE" in failed.text
    assert "assessment provider failed safely" in failed.text
    assert "malformed-v1" not in failed.text
    assert unaffected.status_code == 200
    assert "NOT EVALUABLE" in unaffected.text
    assert "no provider registered for this assessment policy" \
        in unaffected.text


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
    assert "SCHEDULE BUFFER" in hero
    assert "TRAJECTORY" in hero
    assert "DESTINATION" in hero
    assert "low to high sensitivity" in hero
    assert "trajectory-legend" not in hero
    assert "trajectory-shell" not in html
    assert '<h2 id="trajectory-heading">' not in html




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
    assert "Current milestone." in html
    assert "Mission completion milestone." in html
    assert "Estimated " in html
    assert 'aria-describedby="mission-console-summary"' in html
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
    assert ".mission-detail-hero { min-height: 940px;" in html
    assert "height: 510px; justify-content: flex-start;" in html
    assert "inset: 510px -30px 150px -58px;" in html
    assert ".hero-trajectory .milestone-detail { opacity: 0; }" in html
    assert ".trajectory-readout .mono, .trajectory-readout .note" in html
    assert ".mission-milestone:focus .milestone-detail" in html
    assert 'class="mission-time-lane"' not in html
    assert "grid-template-columns: repeat(2, minmax(0,1fr));" in html


def _synthetic_assessment(forecast=(), milestones=None):
    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import (
        MissionAssessment, MissionMilestone, TrajectoryPoint,
    )
    from foundry.core.scope import Subject

    scope = Subject("party", "household-test")
    milestone_values = milestones or (
        MissionMilestone(
            "capital", "Capital Assembly", 0.0, 400.0, .75,
            order=0, unit_or_currency="USD", is_current=True),
        MissionMilestone(
            "velocity", "Velocity Gate", 400.0, 900.0, 0.0,
            order=1, unit_or_currency="USD"),
        MissionMilestone(
            "free", "Choice Point", 900.0, 1_700.0, 0.0,
            order=2, unit_or_currency="USD", completes_mission=True),
        MissionMilestone(
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
        trajectory_state="Nominal",
        current_milestone=milestone_values[0], milestones=milestone_values,
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

    from foundry.core.mission_assessment import ForecastPoint
    from foundry.mission_control import (
        _mission_trajectory_geometry, _mission_trajectory_svg,
    )
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

    # Forecasts beyond the destination must not squeeze every milestone
    # into an unreadable cluster at the start of the mission arc.
    geometry = _mission_trajectory_geometry(_synthetic_assessment((
        ForecastPoint(5.0, 2_000.0, 4_000.0, 8_000.0),
        ForecastPoint(6.0, 4_000.0, 8_000.0, 16_000.0),
    )))
    milestone_x = [point[0] for _, point in geometry["phase_points"]]
    assert all(
        following - current > 60.0
        for current, following in zip(milestone_x, milestone_x[1:])
    )

    source = inspect.getsource(mission_control)
    for forbidden in (
        "finance.financial_independence.v1",
        "Building Capital", "Escape Velocity", "Abundance",
        "450_000", "750_000", "1_500_000",
    ):
        assert forbidden not in source


def test_renderer_preserves_deliberately_supplied_milestone_order():
    import inspect

    from foundry.mission_control import (
        _mission_trajectory_geometry,
        _mission_trajectory_svg,
    )

    assessment = _synthetic_assessment(())
    supplied = (
        assessment.milestones[2],
        assessment.milestones[0],
        assessment.milestones[3],
        assessment.milestones[1],
    )

    geometry = _mission_trajectory_geometry(assessment, supplied)
    rendered = _mission_trajectory_svg(assessment, supplied)

    assert tuple(item.id for item, _ in geometry["phase_points"]) == tuple(
        item.id for item in supplied)
    positions = [rendered.index(item.label.upper()) for item in supplied]
    assert positions == sorted(positions)
    assert "sorted(" not in inspect.getsource(_mission_trajectory_geometry)


def test_current_position_uses_provider_presentation_metadata():
    from dataclasses import replace

    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import TelemetryItem
    from foundry.mission_control import _mission_trajectory_svg

    assessment = _synthetic_assessment(())
    result = MetricResult(
        metric_id="domain.capacity", value=.42,
        unit_or_currency=None, scope=assessment.scope, as_of=4.0,
        status="available", calculation_version="domain-v1")
    assessment = replace(
        assessment,
        current_value=result,
        telemetry=(TelemetryItem(
            result=result,
            label="CAPACITY UTILISATION",
            format_kind="percent",
        ),),
    )

    rendered = _mission_trajectory_svg(assessment)

    assert "CAPACITY UTILISATION 42.0%" in rendered
    assert ">42.0%</text>" in rendered
    assert "$0" not in rendered


def test_hostile_current_value_unit_is_escaped_in_svg():
    from dataclasses import replace

    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import TelemetryItem
    from foundry.mission_control import _mission_trajectory_svg

    assessment = _synthetic_assessment(())
    hostile_unit = "</text><script>alert('unit')</script><text>"
    result = MetricResult(
        metric_id="domain.capacity", value=300.0,
        unit_or_currency=hostile_unit, scope=assessment.scope, as_of=4.0,
        status="available", calculation_version="domain-v1")
    assessment = replace(
        assessment,
        current_value=result,
        telemetry=(TelemetryItem(
            result=result,
            label="CAPACITY",
            format_kind="currency",
        ),),
    )

    rendered = _mission_trajectory_svg(assessment)

    assert "<script>alert('unit')</script>" not in rendered
    assert "&lt;/text&gt;&lt;script&gt;" in rendered


def test_lower_is_better_milestones_advance_without_renderer_branching():
    from foundry.core.mission_assessment import MissionMilestone
    from foundry.mission_control import _mission_trajectory_geometry

    milestones = (
        MissionMilestone(
            "current", "Current", 250.0, 400.0, .5,
            is_current=True, destination_direction="lower_is_better",
            destination_value=250.0),
        MissionMilestone(
            "destination", "Destination", 0.0, 250.0, 0.0,
            order=1, completes_mission=True,
            destination_direction="lower_is_better",
            destination_value=100.0),
    )
    geometry = _mission_trajectory_geometry(
        _synthetic_assessment((), milestones=milestones))
    points = dict(
        (milestone.id, point)
        for milestone, point in geometry["phase_points"]
    )

    assert points["destination"][0] > geometry["current_point"][0]


def test_mission_control_has_no_defined_mission_name_branch():
    import inspect

    import foundry.mission_control as mission_control

    source = inspect.getsource(mission_control)
    for forbidden in (
        "financial-independence",
        "Financial Independence",
        "Mortgage Freedom",
        "Pension Independence",
        "Financial Resilience",
    ):
        assert forbidden not in source


def _replace_demo_scenario(log, *, name, amount, structured=True,
                           unit_or_currency="GBP"):
    from foundry.finance import entities as finance
    from foundry.finance.entities import FinanceEntityProjection

    projection = FinanceEntityProjection(log)
    original = next(
        scenario for scenario in projection.scenarios.values()
        if scenario.status == "active"
        and "monthly_contribution_delta" in scenario.adjustments)
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
    burn = html[
        html.index('<section data-console-region="next-burn"'):
        html.index("</section>", html.index(
            '<section data-console-region="next-burn"'))
    ]
    assert "Increase ISA contribution" in burn
    assert "£375 per month" in burn
    assert "£999" not in burn


def test_user_controlled_scenario_name_does_not_reach_the_console(tmp_path):
    log = _seed_financial_independence(tmp_path)
    _replace_demo_scenario(
        log, name="<script>alert('financial-data')</script>", amount=375.0)

    html = client().get("/missions/financial-independence").text
    assert "<script>alert('financial-data')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;financial-data&#x27;)&lt;/script&gt;" not in html
    assert "Increase ISA contribution" in html


def test_missing_structured_recommendation_data_fails_honestly(tmp_path):
    log = _seed_financial_independence(tmp_path)
    _replace_demo_scenario(
        log, name="Increase ISA by £999", amount=275.0, structured=False)

    html = client().get("/missions/financial-independence").text
    burn = html[
        html.index('<section data-console-region="next-burn"'):
        html.index("</section>", html.index(
            '<section data-console-region="next-burn"'))
    ]
    assert "INSUFFICIENT EVIDENCE" in burn
    assert "The declared recommendation is incomplete." in burn
    assert "£275" not in burn
    assert "£999" not in burn
    assert "Scenario " not in html
    assert "Declared recommendation presentation details are incomplete" \
        in html


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

    assert "CURRENT MILESTONE BUILDING CAPITAL" in card
    assert "TRAJECTORY · ACCELERATED" in card
    assert "MISSION MARGIN HIGH MARGIN" in card
    assert "FROM TARGET" not in card
    assert "TARGET £" not in card

    detail = client().get("/missions/financial-independence").text
    assert "<p class=\"k\">CURRENT POSITION</p>" in detail
    assert "<p class=\"k\">TRAJECTORY</p>" in detail
    assert "SCHEDULE BUFFER" in detail
    assert "SUPPORTED" in detail
    assert "% above required pace" in detail


def test_margin_presentation_does_not_reuse_trajectory_status_colour(
        monkeypatch, tmp_path):
    from foundry.core.metrics import MetricResult
    from foundry.core.mission_assessment import (
        DeltaV, ForecastPoint, MissionAssessment,
        MissionAssessmentRegistry, MissionConfidence, MissionMargin,
        MissionMilestone, TrajectoryPoint,
    )
    from foundry.finance.mission_assessment import POLICY_ID
    from foundry.finance.missions import register_finance_mission_definitions

    _seed_financial_independence(tmp_path)

    class IndependentDimensionsProvider:
        def owned_policy_ids(self):
            return frozenset({POLICY_ID})

        def assess(self, request):
            milestone = MissionMilestone(
                "current", "Current", 0.0, 200.0, .5,
                is_current=True, destination_value=0.0)
            return MissionAssessment(
                mission_id=request.mission_id,
                policy_id=request.policy_id,
                scope=request.scope,
                as_of=request.as_of,
                status="red",
                calculation_version="independent-v1",
                current_value=MetricResult(
                    "finance.accessible_assets", 100.0, "GBP",
                    request.scope, request.as_of, "available",
                    "independent-v1"),
                trajectory_state="Accelerated",
                trajectory_tone="green",
                confidence=MissionConfidence(
                    "Established", "independently verified"),
                mission_margin=MissionMargin(
                    10.0, 10.0, "strong operating buffer", "High Margin"),
                current_milestone=milestone,
                milestones=(milestone,),
                eta=request.as_of + 1.0,
                delta_v=DeltaV(1.0, 1, "test schedule change"),
                trajectory=(TrajectoryPoint(request.as_of, 100.0),),
                forecast=(
                    ForecastPoint(request.as_of, 100.0, 100.0, 100.0),
                ),
            )

    def independent_console():
        console = _build_console()
        assessments = MissionAssessmentRegistry()
        register_finance_mission_definitions(assessments)
        assessments.register(IndependentDimensionsProvider())
        console.assessments = assessments
        return console

    monkeypatch.setattr(app.state, "console_factory", independent_console)

    detail = client().get("/missions/financial-independence").text

    assert '<p class="v green">ACCELERATED TRAJECTORY</p>' in detail
    assert '<p class="v red">ACCELERATED TRAJECTORY</p>' not in detail
    assert '<p class="v num green">High Margin</p>' in detail
    assert '<p class="v num red">HIGH MARGIN</p>' not in detail


def test_console_renderer_preserves_model_region_order_verbatim(tmp_path):
    from types import SimpleNamespace

    from foundry.core.mission_assessment import MissionAssessmentRequest
    from foundry.core.mission_console import MissionConsoleModel
    from foundry.mission_control import (
        TrustedHtml,
        _active_missions,
        _as_of,
        _household_scope,
        _render_mission_console,
    )

    _seed_financial_independence(tmp_path)
    console = _build_console()
    definition = console.assessments.definition_for_slug(
        "financial-independence")
    scope = _household_scope(console)
    mission = next(
        item for item in _active_missions(console)
        if item.assessment_policy_id == definition.assessment_policy_id
    )
    assessment = console.assessments.dispatch(MissionAssessmentRequest(
        mission.id,
        definition.assessment_policy_id,
        scope,
        _as_of(console),
    ))
    view = MissionConsoleModel().build(definition, assessment)
    order = (
        "next-burn",
        "mission-hero",
        "flight-analysis",
        "essential-telemetry",
        "progressive-disclosure",
    )
    deliberately_reordered = SimpleNamespace(
        hero=view.hero,
        analysis=view.analysis,
        essential=view.essential,
        next_burn=view.next_burn,
        disclosure=view.disclosure,
        region_order=order,
    )

    rendered = _render_mission_console(
        deliberately_reordered,
        assessment,
        TrustedHtml('<a href="/missions">BACK</a>'),
        assessment.as_of,
    )

    positions = [
        rendered.index(f'data-console-region="{region}"')
        for region in order
    ]
    assert positions == sorted(positions)


def test_console_model_and_renderer_contain_no_mission_identity_branch():
    import inspect

    import foundry.core.mission_console as mission_console
    import foundry.mission_control as mission_control

    source = inspect.getsource(mission_console) + inspect.getsource(
        mission_control._render_mission_console)
    for identity in (
        "financial-resilience",
        "financial-independence",
        "pension-independence",
        "mortgage-freedom",
        "Financial Resilience",
        "Financial Independence",
        "Pension Independence",
        "Mortgage Freedom",
    ):
        assert identity not in source


def test_console_route_fixture_uses_explicit_clocks_and_no_current_date():
    import ast
    import inspect

    source = inspect.getsource(_seed_financial_independence)
    tree = ast.parse(source)
    build_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build"
    ]

    assert build_calls
    assert all(
        any(keyword.arg == "as_of" for keyword in call.keywords)
        for call in build_calls
    )
    assert "date.today" not in source
    assert "datetime.now" not in source


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
    assert "This mission has not been set up yet." in html
    assert "No assessment is shown until its goal and household" in html


def test_duplicate_active_missions_for_one_definition_fail_closed(tmp_path):
    from foundry.core.entities import EntityProjection

    log = _seed_financial_independence(tmp_path)
    existing = next(
        mission for mission in EntityProjection(log).missions.values()
        if mission.assessment_policy_id
        == "finance.financial_independence.v1")
    declare_mission(
        log,
        "Duplicate policy claim",
        target_metric=existing.target_metric,
        target_value=existing.target_value,
        target_date=existing.target_date,
        tolerance=existing.tolerance,
        assessment_policy_id=existing.assessment_policy_id,
        assumption_set_id=existing.assumption_set_id,
    )

    detail = client().get("/missions/financial-independence")
    home = client().get("/")

    assert detail.status_code == 200
    assert "more than one active" in detail.text
    assert "No mission was selected." in detail.text
    assert "AMBIGUOUS ACTIVE MISSION" in home.text
    assert "Duplicate policy claim · tracked" not in home.text
