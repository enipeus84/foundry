"""Human capture seam for immutable provider pension projections."""

from itertools import count

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.metrics import MetricRequest  # noqa: E402
from foundry.core.scope import Subject  # noqa: E402
from foundry.demo_data import build  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.pension_projection import (  # noqa: E402
    EVENT_KIND,
    PensionProviderProjectionProjection,
)
from foundry.web import app, _build_console  # noqa: E402


ALLOWED = "cparkerbrads@gmail.com"
AS_OF = 1_786_725_200.0


@pytest.fixture(autouse=True)
def capture_env(monkeypatch, tmp_path):
    event_clock = count(AS_OF, step=.001)
    monkeypatch.setattr("foundry.eventlog.time.time", event_clock.__next__)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setattr(app.state, "console_factory", _build_console)


def _client():
    client = TestClient(app)
    client.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(
        ALLOWED, webauth.load_config()))
    return client


def _values(default_account_id, **changes):
    values = {
        "csrf": webauth.csrf_token(
            ALLOWED, webauth.load_config(), "pension-projection-capture"),
        "account_id": default_account_id,
        "provider": "Aviva",
        "observed_at": "2026-08-12T10:30",
        "retirement_age": "68",
        "fund_low": "380000",
        "fund_medium": "604000",
        "fund_high": "1100000",
        "income_low": "22500",
        "income_medium": "43800",
        "income_high": "96600",
        "growth_low_percent": "-0.8",
        "growth_medium_percent": "2.2",
        "growth_high_percent": "5.1",
        "income_basis": "Provider-stated annuity illustration",
        "source": "Aviva pension illustration",
        "lineage": "Household supplied statement",
    }
    values.update(changes)
    return values


def _seed(tmp_path):
    return build(EventLog(tmp_path / "events.jsonl"), as_of=AS_OF)


def _economic_values(household):
    console = _build_console()
    scope = Subject("party", household.household_id)
    mission = next(mission for mission in console.entities.missions.values()
                   if mission.assessment_policy_id == "finance.pension_independence.v1")
    net_worth = console.registry.dispatch(MetricRequest(
        "finance.net_worth", scope, AS_OF)).value
    pension = console.registry.dispatch(MetricRequest(
        "finance.pension_wealth", scope, AS_OF,
        assumption_set_id=mission.assumption_set_id)).value
    return net_worth, pension


def test_capture_review_confirm_and_latest_projection_reaches_mission(tmp_path):
    household = _seed(tmp_path)
    client = _client()
    before = _economic_values(household)

    chooser = client.get("/operations/capture")
    assert "Pension Projection Update" in chooser.text
    form = client.get("/operations/pension-projection")
    assert form.status_code == 200
    assert "Alex&#x27;s workplace pension" in form.text
    assert "Sam&#x27;s workplace pension" in form.text
    assert "Choose a pension account" in form.text
    assert 'value="Aviva"' in form.text
    assert "Unix timestamp" not in form.text

    values = _values(household.alex_pension_id)
    review = client.post("/operations/pension-projection/review", data=values)
    assert review.status_code == 200
    assert "Review Aviva pension projection" in review.text
    assert "As at: 12 August 2026" in review.text
    assert "Medium £604,000" in review.text
    assert "Low -0.8% · Medium 2.2% · High 5.1%" in review.text
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())

    confirmation = client.post(
        "/operations/pension-projection/confirm", data=values)
    assert confirmation.status_code == 200
    assert "Aviva pension projection recorded" in confirmation.text
    assert "Retirement age: 68" in confirmation.text
    assert "Medium £604,000" in confirmation.text
    assert "Medium £43,800" in confirmation.text
    assert 'href="/missions/pension-independence"' in confirmation.text

    log = EventLog(tmp_path / "events.jsonl")
    projection_events = [event for event in log.events() if event["kind"] == EVENT_KIND]
    assert len(projection_events) == 1
    assert projection_events[0]["payload"]["account_id"] == household.alex_pension_id
    assert projection_events[0]["payload"]["growth_low_percent"] == -.8
    assert _economic_values(household) == before

    mission = client.get("/missions/pension-independence")
    assert "£604,000" in mission.text
    assert "£43,800" in mission.text
    assert "AVIVA · OBSERVED 2026-08-12" in mission.text

    newer = _values(
        household.alex_pension_id, observed_at="2026-08-13T10:30",
        fund_medium="650000", fund_high="1150000",
        income_medium="47000", income_high="99000",
        growth_medium_percent="2.5", growth_high_percent="5.4")
    assert client.post(
        "/operations/pension-projection/confirm", data=newer).status_code == 200
    history = PensionProviderProjectionProjection(EventLog(tmp_path / "events.jsonl"))
    assert len(history.for_account(household.alex_pension_id, AS_OF)) == 2
    mission = client.get("/missions/pension-independence")
    assert "£650,000" in mission.text
    assert "£47,000" in mission.text


@pytest.mark.parametrize("changes", (
    {"account_id": ""},
    {"provider": ""},
    {"observed_at": "not-a-date"},
    {"retirement_at": "2028-01-01"},
    {"retirement_age": ""},
    {"fund_low": "-1"},
    {"fund_low": "700000"},
    {"income_medium": "10000"},
    {"growth_medium_percent": "-1"},
    {"income_basis": ""},
    {"source": ""},
    {"lineage": ""},
))
def test_capture_refuses_invalid_provider_projection(tmp_path, changes):
    household = _seed(tmp_path)
    values = _values(household.alex_pension_id, **changes)

    response = _client().post(
        "/operations/pension-projection/confirm", data=values)

    assert response.status_code in {400, 404}
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())
