"""TELMU matrix for RFC-016 Phase 3 Mission Target Management."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.entities import (  # noqa: E402
    abandon_mission,
    achieve_mission,
    declare_mission,
    declare_party,
    join_household,
)
from foundry.core.mission_targets import (  # noqa: E402
    MissionTargetProjection,
    TargetQuantity,
)
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.mission_assessment import POLICY_ID  # noqa: E402
from foundry.finance.pension_assessment import POLICY_ID as PENSION_POLICY_ID  # noqa: E402
from foundry.finance.resilience_assessment import POLICY_ID as RESILIENCE_POLICY_ID  # noqa: E402
from foundry.finance.mission_targets import FinanceTargetMetricResolver  # noqa: E402
from foundry.mission_targets_web import (  # noqa: E402
    _DECLARE_PURPOSE,
    _REVIEW_PURPOSE,
    _WITHDRAW_PURPOSE,
)
from foundry.web import _build_console, app  # noqa: E402


ALLOWED = "operator@example.com"
START = 2_000_000_000.0


@pytest.fixture(autouse=True)
def phase3_env(monkeypatch, tmp_path):
    clock = count(START, step=1.0)
    monkeypatch.setattr("foundry.eventlog.time.time", clock.__next__)
    monkeypatch.setattr("foundry.mission_targets_web.time.time", clock.__next__)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setattr(app.state, "console_factory", _build_console)


def _client(*, email: str = ALLOWED) -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(
        webauth.SESSION_COOKIE,
        webauth.session_token(email, webauth.load_config()),
    )
    return client


def _token(purpose: str) -> str:
    return webauth.csrf_token(ALLOWED, webauth.load_config(), purpose)


def _log(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "events.jsonl")


def _seed(tmp_path: Path, *, metric_id: str = "finance.accessible_assets",
          policy_id: str = POLICY_ID):
    log = _log(tmp_path)
    household = declare_party(log, "household")
    mission = declare_mission(
        log,
        "Household destination",
        target_metric=metric_id,
        assessment_policy_id=policy_id,
    )
    return log, household, mission


def _declare_data(mission_id: str, *, subject_id: str | None = None, value: str = "750000",
                  reviewed: str = "none", purpose: str = _DECLARE_PURPOSE,
                  basis: str = "Deliberate long-term destination") -> dict[str, str]:
    household_id = next(party.id for party in _build_console().entities.parties.values()
                        if party.party_type == "household" and party.status == "active")
    return {
        "csrf": _token(purpose),
        "mission_id": mission_id,
        "subject_id": subject_id or household_id,
        "destination_value": value,
        "horizon_date": "2035-01-01",
        "basis": basis,
        "reviewed_in_force": reviewed,
    }


def _review_data(mission_id: str, *, value: str = "750000",
                 basis: str = "Deliberate long-term destination") -> dict[str, str]:
    household_id = next(party.id for party in _build_console().entities.parties.values()
                        if party.party_type == "household" and party.status == "active")
    return {
        "csrf": _token(_REVIEW_PURPOSE),
        "mission_id": mission_id,
        "subject_id": household_id,
        "destination_value": value,
        "horizon_date": "2035-01-01",
        "basis": basis,
    }


def _projection() -> MissionTargetProjection:
    projection = _build_console().mission_targets
    assert isinstance(projection, MissionTargetProjection)
    return projection


def _direct_declare(household_id: str, mission_id: str, *, value: float = 750_000,
                    supersedes: str | None = None):
    projection = _projection()
    descriptor = projection.metric_resolver.describe("finance.accessible_assets")
    return projection.declare(
        household_id=household_id, subject_id=household_id,
        mission_id=mission_id,
        metric_id="finance.accessible_assets",
        destination=TargetQuantity(value, descriptor.unit_or_currency, descriptor.dimension),
        destination_direction=descriptor.destination_direction,
        horizon_kind="by_date",
        horizon_at=datetime(2035, 1, 1, tzinfo=timezone.utc).timestamp(),
        effective_from=START + 2,
        supersedes=supersedes,
    )


def _target_events(log: EventLog) -> list[dict]:
    return [event for event in log.events()
            if event["kind"].startswith("core.mission_target.")]


def test_first_declaration_derives_canonical_event_and_replays_deterministically(tmp_path):
    log, household, mission = _seed(tmp_path)
    response = _client().post(
        "/missions/targets/declare", data=_declare_data(mission.id))
    assert response.status_code == 303
    events = _target_events(log)
    assert [event["kind"] for event in events] == ["core.mission_target.declared"]
    payload = events[0]["payload"]
    assert payload == {
        "entity_id": payload["entity_id"],
        "mission_id": mission.id,
        "household_id": household.id,
        "subject_id": household.id,
        "metric_id": "finance.accessible_assets",
        "destination_value": 750_000.0,
        "destination_unit": "GBP",
        "destination_dimension": "currency",
        "destination_direction": "higher_is_better",
        "horizon_kind": "by_date",
        "horizon_at": datetime(2035, 1, 1, tzinfo=timezone.utc).timestamp(),
        "effective_from": payload["effective_from"],
        "basis": "Deliberate long-term destination",
    }
    first = _projection().in_force(mission.id, START + 1_000)
    replay = _projection().in_force(mission.id, START + 10_000)
    assert first == replay


def test_ui_submits_selected_active_member_subject(tmp_path):
    log, household, mission = _seed(tmp_path)
    member = declare_party(log, "person")
    join_household(log, member.id, household.id)

    form = _client().get(f"/missions/targets/new?mission={mission.id}")
    assert form.status_code == 200
    assert f'name="subject_id"' in form.text
    assert f'value="{member.id}"' in form.text

    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, subject_id=member.id),
    )
    assert response.status_code == 303
    assert _target_events(log)[0]["payload"]["subject_id"] == member.id


def test_ui_refuses_missing_subject(tmp_path):
    _, _, mission = _seed(tmp_path)
    data = _declare_data(mission.id)
    del data["subject_id"]
    assert _client().post("/missions/targets/declare", data=data).status_code == 403


def test_replacement_supersedes_current_server_derived_predecessor(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, value="900000", reviewed=first.id),
    )
    assert response.status_code == 303
    projection = _projection()
    successor = projection.in_force(mission.id, START + 10_000)
    assert successor is not None and successor.supersedes == first.id
    assert projection.targets[first.id].id == first.id
    assert [event["kind"] for event in _target_events(log)] == [
        "core.mission_target.declared", "core.mission_target.declared"]


def test_withdrawal_appends_generic_close_and_removes_current_target(tmp_path):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    response = _client().post("/missions/targets/withdraw", data={
        "csrf": _token(_WITHDRAW_PURPOSE),
        "target_id": target.id,
        "reviewed_in_force": target.id,
        "reason": "Destination no longer applies",
    })
    assert response.status_code == 303
    closed = _target_events(log)[-1]
    assert closed["kind"] == "core.mission_target.closed"
    assert closed["payload"] == {
        "entity_id": target.id,
        "reason": "Destination no longer applies",
    }
    assert _projection().in_force(mission.id, START + 10_000) is None


def test_review_is_read_only_and_escapes_permanent_basis(tmp_path):
    log, _, mission = _seed(tmp_path)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/review",
        data=_review_data(mission.id, basis='<script>alert("x")</script>'),
    )
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text and "<script>alert" not in response.text
    assert "permanent append-only canonical history" in response.text
    assert log.path.read_bytes() == before


def test_effective_from_is_computed_at_approval_not_carried_from_review(
        tmp_path, monkeypatch):
    log, _, mission = _seed(tmp_path)
    moments = iter((START + 100, START + 101, START + 200, START + 201))
    monkeypatch.setattr("foundry.mission_targets_web._now", lambda: next(moments))
    review = _client().post(
        "/missions/targets/review", data=_review_data(mission.id))
    assert review.status_code == 200
    assert 'name="effective_from"' not in review.text
    approval = _client().post(
        "/missions/targets/declare", data=_declare_data(mission.id))
    assert approval.status_code == 303
    payload = _target_events(log)[0]["payload"]
    assert payload["effective_from"] == START + 201


def test_stale_none_double_submit_is_refused_without_second_append(tmp_path):
    log, _, mission = _seed(tmp_path)
    client = _client()
    data = _declare_data(mission.id)
    assert client.post("/missions/targets/declare", data=data).status_code == 303
    before = log.path.read_bytes()
    assert client.post("/missions/targets/declare", data=data).status_code == 409
    assert log.path.read_bytes() == before


def test_stale_predecessor_after_concurrent_tab_declaration_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    second = _direct_declare(household.id, mission.id, value=800_000, supersedes=first.id)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert second.id != first.id and response.status_code == 409
    assert log.path.read_bytes() == before


def test_stale_after_withdrawal_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    _projection().withdraw(
        household_id=household.id, target_id=first.id, reason="other tab")
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert response.status_code == 409
    assert log.path.read_bytes() == before


def test_stale_after_supersession_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    _direct_declare(household.id, mission.id, value=850_000, supersedes=first.id)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert response.status_code == 409
    assert log.path.read_bytes() == before


def test_stale_after_mission_closed_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    abandon_mission(log, mission.id, "closed elsewhere")
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert response.status_code in {404, 409}
    assert log.path.read_bytes() == before


def test_stale_after_conflict_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    payload = next(event["payload"].copy() for event in log.events()
                   if event["kind"] == "core.mission_target.declared")
    payload["entity_id"] = "concurrent-conflict"
    log.append("core.mission_target.declared", payload)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert response.status_code == 409
    assert log.path.read_bytes() == before


def test_fresh_review_after_stale_refusal_can_replace_current(tmp_path):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    second = _direct_declare(household.id, mission.id, value=800_000, supersedes=first.id)
    stale = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert stale.status_code == 409
    fresh = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, value="950000", reviewed=second.id),
    )
    assert fresh.status_code == 303
    assert _projection().in_force(mission.id, START + 10_000).supersedes == second.id
    assert len(_target_events(log)) == 3


def test_withdrawal_review_becomes_stale_after_target_is_withdrawn(tmp_path):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    _projection().withdraw(
        household_id=household.id, target_id=target.id, reason="other tab")
    before = log.path.read_bytes()
    response = _client().post("/missions/targets/withdraw", data={
        "csrf": _token(_WITHDRAW_PURPOSE),
        "target_id": target.id,
        "reviewed_in_force": target.id,
        "reason": "stale approval",
    })
    assert response.status_code == 409
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("field", [
    "household_id", "metric_id", "supersedes", "effective_from",
    "destination_unit", "destination_dimension", "destination_direction",
    "horizon_kind", "horizon_at", "tolerance", "tolerance_value",
])
def test_derived_fields_are_never_accepted_as_client_authority(tmp_path, field):
    log, _, mission = _seed(tmp_path)
    data = _declare_data(mission.id)
    data[field] = "forged"
    before = log.path.read_bytes()
    assert _client().post("/missions/targets/declare", data=data).status_code == 403
    assert log.path.read_bytes() == before


def test_forged_staleness_assertion_can_only_refuse_not_control_supersedes(tmp_path):
    log, household, mission = _seed(tmp_path)
    current = _direct_declare(household.id, mission.id)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed="forged-predecessor"),
    )
    assert current.id not in response.text and response.status_code == 409
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("value", ["not-a-number", "nan", "inf", "-inf"])
def test_non_numeric_and_non_finite_destinations_are_refused(tmp_path, value):
    log, _, mission = _seed(tmp_path)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare", data=_declare_data(mission.id, value=value))
    assert response.status_code in {400, 409}
    assert log.path.read_bytes() == before


def test_basis_boundary_accepts_500_unicode_characters_and_refuses_501(tmp_path):
    log, _, mission = _seed(tmp_path)
    accepted = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, basis="£" * 500),
    )
    assert accepted.status_code == 303
    target = _projection().in_force(mission.id, START + 10_000)
    before = log.path.read_bytes()
    refused = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=target.id, basis="£" * 501),
    )
    assert refused.status_code == 409
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("horizon", ["not-a-date", "2035-02-30", "10000-01-01"])
def test_unparseable_and_out_of_range_horizon_dates_are_refused(tmp_path, horizon):
    log, _, mission = _seed(tmp_path)
    data = _declare_data(mission.id)
    data["horizon_date"] = horizon
    before = log.path.read_bytes()
    assert _client().post("/missions/targets/declare", data=data).status_code in {400, 409}
    assert log.path.read_bytes() == before


def test_empty_withdrawal_reason_is_refused(tmp_path):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    before = log.path.read_bytes()
    response = _client().post("/missions/targets/withdraw", data={
        "csrf": _token(_WITHDRAW_PURPOSE), "target_id": target.id,
        "reviewed_in_force": target.id, "reason": "",
    })
    assert response.status_code == 409
    assert log.path.read_bytes() == before


def test_wrong_content_type_and_multivalued_fields_are_refused(tmp_path):
    log, _, mission = _seed(tmp_path)
    client = _client()
    before = log.path.read_bytes()
    wrong_type = client.post(
        "/missions/targets/declare", json=_declare_data(mission.id))
    assert wrong_type.status_code == 403
    encoded = (f"csrf={_token(_DECLARE_PURPOSE)}&mission_id={mission.id}"
               "&destination_value=1&destination_value=2&horizon_date=2035-01-01"
               "&basis=&reviewed_in_force=none")
    repeated = client.post(
        "/missions/targets/declare",
        content=encoded,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert repeated.status_code == 403
    assert log.path.read_bytes() == before


def test_unknown_mission_query_parameter_is_refused(tmp_path):
    _seed(tmp_path)
    assert _client().get("/missions/targets/new?mission=unknown").status_code == 404


@pytest.mark.parametrize("route", [
    ("get", "/missions"),
    ("get", "/missions/targets/new?mission=x"),
    ("post", "/missions/targets/review"),
    ("post", "/missions/targets/declare"),
    ("get", "/missions/targets/x/withdraw"),
    ("post", "/missions/targets/withdraw"),
])
def test_every_phase3_route_requires_authentication(route):
    method, path = route
    response = getattr(TestClient(app, follow_redirects=False), method)(path)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_wrong_email_is_refused(tmp_path):
    _, _, mission = _seed(tmp_path)
    assert _client(email="intruder@example.com").get(
        f"/missions/targets/new?mission={mission.id}").status_code == 303


@pytest.mark.parametrize("purpose", [
    _REVIEW_PURPOSE, "rfc013-capture", "rfc011-confirmation", "rfc012-capture",
])
def test_non_declare_csrf_purposes_are_not_transferable_to_approval(tmp_path, purpose):
    log, _, mission = _seed(tmp_path)
    before = log.path.read_bytes()
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, purpose=purpose),
    )
    assert response.status_code == 403
    assert log.path.read_bytes() == before


def test_absent_and_expired_csrf_are_refused(tmp_path):
    log, _, mission = _seed(tmp_path)
    before = log.path.read_bytes()
    absent = _declare_data(mission.id)
    absent["csrf"] = ""
    expired = _declare_data(mission.id)
    expired["csrf"] = webauth.sign(
        {"email": ALLOWED, "purpose": _DECLARE_PURPOSE, "exp": 0},
        webauth.load_config().session_secret,
    )
    assert _client().post("/missions/targets/declare", data=absent).status_code == 403
    assert _client().post("/missions/targets/declare", data=expired).status_code == 403
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("purpose", [
    _REVIEW_PURPOSE, _DECLARE_PURPOSE, "rfc013-capture", "rfc011-confirmation",
])
def test_non_withdraw_csrf_purposes_are_not_transferable_to_withdrawal(
        tmp_path, purpose):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    before = log.path.read_bytes()
    response = _client().post("/missions/targets/withdraw", data={
        "csrf": _token(purpose), "target_id": target.id,
        "reviewed_in_force": target.id, "reason": "forged purpose",
    })
    assert response.status_code == 403
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("close", [achieve_mission, abandon_mission])
def test_inactive_mission_declaration_and_withdrawal_are_refused(tmp_path, close):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    close(log, mission.id, "inactive")
    before = log.path.read_bytes()
    declaration = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=target.id),
    )
    withdrawal = _client().post("/missions/targets/withdraw", data={
        "csrf": _token(_WITHDRAW_PURPOSE), "target_id": target.id,
        "reviewed_in_force": target.id, "reason": "crafted request",
    })
    assert declaration.status_code in {404, 409}
    assert withdrawal.status_code in {404, 409}
    assert log.path.read_bytes() == before


def test_another_households_bound_mission_and_target_are_not_disclosed(tmp_path):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    declare_party(log, "household")  # most recent active household is now different
    before = log.path.read_bytes()
    page = _client().get("/missions")
    withdrawal = _client().get(f"/missions/targets/{target.id}/withdraw")
    assert target.id not in page.text
    assert withdrawal.status_code == 404
    assert log.path.read_bytes() == before


def test_unknown_metric_and_missing_horizon_mapping_are_honest_and_read_only(
        tmp_path, monkeypatch):
    log, _, mission = _seed(tmp_path)
    before = log.path.read_bytes()
    monkeypatch.setattr(FinanceTargetMetricResolver, "_HORIZON_KINDS", {})
    page = _client().get("/missions")
    assert "does not have complete target semantics" in page.text
    assert _client().get(
        f"/missions/targets/new?mission={mission.id}").status_code == 404
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("hostile", ["duplicate", "fork", "cycle", "updated"])
def test_hostile_target_log_renders_conflict_and_refuses_every_write(
        tmp_path, hostile):
    log, household, mission = _seed(tmp_path)
    first = _direct_declare(household.id, mission.id)
    payload = next(event["payload"].copy() for event in log.events()
                   if event["kind"] == "core.mission_target.declared")
    if hostile == "duplicate":
        log.append("core.mission_target.declared", {**payload, "entity_id": "duplicate"})
    elif hostile == "fork":
        log.append("core.mission_target.declared", {
            **payload, "entity_id": "fork-a", "supersedes": first.id})
        log.append("core.mission_target.declared", {
            **payload, "entity_id": "fork-b", "supersedes": first.id})
    elif hostile == "cycle":
        log.append("core.mission_target.declared", {
            **payload, "entity_id": "cycle-a", "supersedes": "cycle-b"})
        log.append("core.mission_target.declared", {
            **payload, "entity_id": "cycle-b", "supersedes": "cycle-a"})
    else:
        log.append("core.mission_target.updated", {
            "entity_id": first.id, "reason": "prohibited"})
    before = log.path.read_bytes()
    page = _client().get("/missions")
    assert "conflicted" in page.text and "No lifecycle action" in page.text
    response = _client().post(
        "/missions/targets/declare",
        data=_declare_data(mission.id, reviewed=first.id),
    )
    assert response.status_code == 409
    assert log.path.read_bytes() == before


@pytest.mark.parametrize("world", ["no_household", "no_mission", "no_descriptor"])
def test_empty_and_degraded_worlds_render_with_zero_writes_and_no_fabrication(
        tmp_path, world):
    log = _log(tmp_path)
    if world != "no_household":
        declare_party(log, "household")
    if world == "no_descriptor":
        declare_mission(
            log, "Unknown semantics", target_metric="unknown.metric",
            assessment_policy_id=POLICY_ID)
    before = log.path.read_bytes()
    response = _client().get("/missions")
    assert response.status_code == 200
    assert log.path.read_bytes() == before
    assert not _target_events(log)
    assert not [event for event in log.events()
                if event["kind"] == "core.mission.declared"] if world != "no_descriptor" else True


def test_rendering_every_phase3_read_surface_and_review_appends_nothing(tmp_path):
    log, household, mission = _seed(tmp_path)
    target = _direct_declare(household.id, mission.id)
    before = log.path.read_bytes()
    client = _client()
    assert client.get("/missions").status_code == 200
    assert client.get(f"/missions/targets/new?mission={mission.id}").status_code == 200
    assert client.post(
        "/missions/targets/review",
        data=_review_data(mission.id, value="800000"),
    ).status_code == 200
    assert client.get(f"/missions/targets/{target.id}/withdraw").status_code == 200
    assert log.path.read_bytes() == before


def test_horizon_kind_is_derived_for_all_locked_finance_metrics():
    resolver = FinanceTargetMetricResolver()
    assert resolver.horizon_kind("finance.liquidity_runway") == "none"
    assert resolver.horizon_kind("finance.accessible_assets") == "by_date"
    assert resolver.horizon_kind("finance.pension_wealth") == "derived"
    assert resolver.horizon_kind("finance.mortgage_balance") == "by_date"
    assert resolver.horizon_kind("unknown.metric") is None


@pytest.mark.parametrize(("metric_id", "policy_id", "value", "unit", "kind"), [
    ("finance.liquidity_runway", RESILIENCE_POLICY_ID, "24", "months", "none"),
    ("finance.pension_wealth", PENSION_POLICY_ID, "1000000", "GBP", "derived"),
])
def test_non_dated_horizons_are_derived_and_append_no_horizon_at(
        tmp_path, metric_id, policy_id, value, unit, kind):
    log, household, mission = _seed(
        tmp_path, metric_id=metric_id, policy_id=policy_id)
    response = _client().post("/missions/targets/declare", data={
        "csrf": _token(_DECLARE_PURPOSE),
        "mission_id": mission.id,
        "subject_id": household.id,
        "destination_value": value,
        "basis": "",
        "reviewed_in_force": "none",
    })
    assert response.status_code == 303
    payload = _target_events(log)[0]["payload"]
    assert payload["household_id"] == household.id
    assert payload["destination_unit"] == unit
    assert payload["horizon_kind"] == kind
    assert "horizon_at" not in payload


def test_dedicated_module_has_no_acquisition_stack_imports_and_only_frozen_events():
    source = (Path(__file__).resolve().parents[1]
              / "src/foundry/mission_targets_web.py").read_text()
    assert "operations_web" not in source
    assert "acquisition_web" not in source
    assert "core.mission_target.updated" not in source
    assert "core.mission_target.declared" not in source
    assert "core.mission_target.closed" not in source
