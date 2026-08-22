"""Human capture seam for immutable provider pension projections."""

from itertools import count
import html as html_module
import re
import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.metrics import MetricRequest  # noqa: E402
from foundry.core.mission_assessment import MissionAssessmentRequest  # noqa: E402
from foundry.core.scope import Subject  # noqa: E402
from foundry.demo_data import build  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.pension_projection import (  # noqa: E402
    EVENT_KIND,
    PensionProviderProjectionProjection,
    record_pension_provider_projection,
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


def _confirmation_fields(review):
    token = re.search(r'name="review_token" value="([^"]+)"', review.text)
    csrf = re.search(r'name="csrf" value="([^"]+)"', review.text)
    assert token and csrf
    return {
        "csrf": html_module.unescape(csrf.group(1)),
        "review_token": html_module.unescape(token.group(1)),
    }


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
    console = _build_console()
    mission_definition = next(item for item in console.entities.missions.values()
                              if item.assessment_policy_id == "finance.pension_independence.v1")
    planning_at = console.assessments.dispatch(MissionAssessmentRequest(
        mission_definition.id, mission_definition.assessment_policy_id,
        Subject("party", household.household_id), AS_OF)).forecast[-1].at

    chooser = client.get("/operations/capture")
    assert "Pension Projection Update" in chooser.text
    form = client.get("/operations/pension-projection")
    assert form.status_code == 200
    assert "Alex&#x27;s workplace pension" in form.text
    assert "Sam&#x27;s workplace pension" in form.text
    assert "Choose a pension account" in form.text
    assert 'value="Aviva"' in form.text
    assert "Unix timestamp" not in form.text

    values = _values(household.alex_pension_id, retirement_age="",
                     retirement_at=time.strftime("%Y-%m-%d", time.gmtime(planning_at)))
    review = client.post("/operations/pension-projection/review", data=values)
    assert review.status_code == 200
    assert "Review Aviva pension projection" in review.text
    assert "As at: 12 August 2026" in review.text
    assert "Medium £604,000" in review.text
    assert "Low -0.8% · Medium 2.2% · High 5.1%" in review.text
    assert 'name="fund_medium"' not in review.text
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())

    confirmation_fields = _confirmation_fields(review)
    tampered = client.post("/operations/pension-projection/confirm", data={
        **confirmation_fields, "fund_medium": "650000",
    })
    assert tampered.status_code == 403
    wrong_account = client.post("/operations/pension-projection/confirm", data={
        **confirmation_fields, "account_id": household.sam_pension_id,
    })
    assert wrong_account.status_code == 403
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())

    confirmation = client.post(
        "/operations/pension-projection/confirm", data=confirmation_fields)
    assert confirmation.status_code == 200
    assert "Aviva pension projection recorded" in confirmation.text
    assert "Retirement date:" in confirmation.text
    assert "Medium £604,000" in confirmation.text
    assert "Medium £43,800" in confirmation.text
    assert 'href="/missions/pension-independence"' in confirmation.text

    log = EventLog(tmp_path / "events.jsonl")
    projection_events = [event for event in log.events() if event["kind"] == EVENT_KIND]
    assert len(projection_events) == 1
    assert len([event for event in log.events()
                if event["kind"] == "operations.pension_projection_review.consumed"]) == 1
    assert projection_events[0]["payload"]["account_id"] == household.alex_pension_id
    assert projection_events[0]["payload"]["fund_medium"] == 604_000
    assert projection_events[0]["payload"]["growth_low_percent"] == -.8
    assert _economic_values(household) == before

    record_pension_provider_projection(
        log, household.sam_pension_id, provider="Aviva", currency="GBP", observed_at=AS_OF,
        retirement_at=planning_at, fund_low=200_000, fund_medium=401_000, fund_high=700_000,
        income_low=10_000, income_medium=20_000, income_high=30_000,
        growth_low_percent=-.8, growth_medium_percent=2.2, growth_high_percent=5.1,
        income_basis="Provider-stated income basis", source="Aviva statement",
        lineage="household supplied statement")

    mission = client.get("/missions/pension-independence")
    assert "£1,005,000" in mission.text
    assert "PROJECTED FUND VALUE" in mission.text

    repeated = client.post(
        "/operations/pension-projection/confirm", data=confirmation_fields)
    assert repeated.status_code == 403
    assert len([event for event in EventLog(tmp_path / "events.jsonl").events()
                if event["kind"] == EVENT_KIND]) == 2

    newer = _values(
        household.alex_pension_id, observed_at="2026-08-13T10:30",
        retirement_age="", retirement_at=time.strftime("%Y-%m-%d", time.gmtime(planning_at)),
        fund_medium="650000", fund_high="1150000",
        income_medium="47000", income_high="99000",
        growth_medium_percent="2.5", growth_high_percent="5.4")
    newer_review = client.post(
        "/operations/pension-projection/review", data=newer)
    assert client.post("/operations/pension-projection/confirm",
                       data=_confirmation_fields(newer_review)).status_code == 200
    history = PensionProviderProjectionProjection(EventLog(tmp_path / "events.jsonl"))
    assert len(history.for_account(household.alex_pension_id, AS_OF)) == 2
    mission = client.get("/missions/pension-independence")
    assert "£1,051,000" in mission.text


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
        "/operations/pension-projection/review", data=values)

    assert response.status_code in {400, 404}
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())


def test_confirm_requires_valid_unexpired_review_state(tmp_path, monkeypatch):
    household = _seed(tmp_path)
    client = _client()
    csrf = webauth.csrf_token(
        ALLOWED, webauth.load_config(), "pension-projection-capture")

    direct = client.post("/operations/pension-projection/confirm", data={
        "csrf": csrf, "review_token": "not-a-review-token",
    })
    assert direct.status_code == 403

    review = client.post(
        "/operations/pension-projection/review",
        data=_values(household.alex_pension_id))
    confirmation = _confirmation_fields(review)
    future = time.time() + 700
    monkeypatch.setattr("foundry.webauth.time.time", lambda: future)
    confirmation["csrf"] = webauth.csrf_token(
        ALLOWED, webauth.load_config(), "pension-projection-capture")

    expired = client.post(
        "/operations/pension-projection/confirm", data=confirmation)

    assert expired.status_code == 403
    assert not any(event["kind"] == EVENT_KIND
                   for event in EventLog(tmp_path / "events.jsonl").events())
