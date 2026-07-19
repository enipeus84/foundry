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

KPI_METRIC_IDS = {
    "finance.net_worth", "finance.liquidity_runway",
    "finance.employer_concentration", "finance.debt_ratio",
    "finance.cash_available",
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
    assert KPI_METRIC_IDS <= set(dispatched)
    # And the values on the page are the registry's, not literals:
    assert "£480,760" in r.text          # net worth, computed by Finance
    assert "£18,960" in r.text           # cash available (liquid accounts)
    assert "32.4%" in r.text             # employer concentration


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
    assert r.text.count("UNSUPPORTED") >= 5  # all five cards, honestly
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


def test_home_shows_green_mission_status_and_next_decision(tmp_path):
    """Seeded state: net worth £480,760 vs target £450k ±£50k →
    on_track → GREEN — evaluated by Core, only rendered here. The
    recommendation Claim surfaces as NEXT DECISION via the Evidence
    Index."""
    _seed(tmp_path)
    html = client().get("/").text
    assert "GREEN" in html
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
