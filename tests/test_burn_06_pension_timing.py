"""Steve Recovery Burn 06: canonical pension timing and adult scope."""

from datetime import date, datetime, timezone
from itertools import count

import pytest

from foundry.application.pension_mission import PensionMissionQueryError, PensionMissionQueryService
from foundry.application.pension_timing import PensionTimingError, PensionTimingService
from foundry.core.entities import EntityProjection, declare_party, join_household
from foundry.core.identity import PersonIdentityError, age_years, declare_person_date_of_birth
from foundry.core.metrics import MetricRegistry
from foundry.core.mission_assessment import MissionAssessmentRequest
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.core.scope import Subject
from foundry.demo_data import build
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.pension_assessment import POLICY_ID, PensionIndependenceAssessor
from foundry.finance.pension_evidence import PensionEvidenceProjection, record_pension_evidence
from foundry.finance.pension_metrics import FinancePensionMetricProvider
from foundry.core.mission_assessment import MissionAssessmentRegistry


AS_OF = datetime(2026, 8, 21, 23, tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def deterministic_event_clock(monkeypatch):
    """Keep fixture declarations before their fixed assessment time."""
    event_clock = count(AS_OF - 10_000, step=.001)
    monkeypatch.setattr("foundry.eventlog.time.time", event_clock.__next__)


def _world(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log, as_of=AS_OF)
    core = EntityProjection(log)
    mission = next(item for item in core.missions.values()
                   if item.assessment_policy_id == POLICY_ID)
    return log, household, mission


def _assessor(log):
    core = EntityProjection(log)
    fin = finance.FinanceEntityProjection(log)
    evidence = PensionEvidenceProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(fin, core))
    metrics.register(FinancePensionMetricProvider(fin, core, evidence))
    return PensionIndependenceAssessor(metrics, fin, core, evidence)


def _target(log, household_id, mission, subject_id):
    core = EntityProjection(log)
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    projection = MissionTargetProjection(log, core, definitions, FinanceTargetMetricResolver())
    descriptor = projection.metric_resolver.describe(mission.target_metric)
    return projection.declare(
        household_id=household_id, subject_id=subject_id, mission_id=mission.id,
        metric_id=mission.target_metric,
        destination=TargetQuantity(735_000, descriptor.unit_or_currency, descriptor.dimension),
        destination_direction=descriptor.destination_direction, horizon_kind="derived",
        horizon_at=None, effective_from=AS_OF - 1, actor="test")


def test_dob_is_typed_correctable_and_age_uses_calendar_birthdays(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = declare_party(log, "household"), declare_party(log, "person")
    join_household(log, person.id, household.id)
    first = declare_person_date_of_birth(log, person.id, "2008-02-29", actor="test")
    second = declare_person_date_of_birth(log, person.id, "2008-03-01", actor="test")
    projected = EntityProjection(log).parties[person.id]
    assert projected.date_of_birth == date(2008, 3, 1)
    assert projected.date_of_birth_provenance == [first["id"], second["id"]]
    leap = date(2008, 2, 29)
    assert age_years(leap, datetime(2025, 2, 28, tzinfo=timezone.utc).timestamp()) == 16
    assert age_years(leap, datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp()) == 17
    with pytest.raises(PersonIdentityError):
        declare_person_date_of_birth(log, person.id, "2999-01-01")
    with pytest.raises(PersonIdentityError):
        declare_person_date_of_birth(log, person.id, "not-a-date")


def test_household_scope_includes_adults_only_and_requires_all_dobs(tmp_path):
    log, household, mission = _world(tmp_path)
    core = EntityProjection(log)
    child = core.parties[household.emily_id]
    child_pension = finance.declare_account(log, "pension", "GBP")
    finance.link_ownership(log, "account", child_pension.id, "owner", child.id)
    finance.declare_valuation(log, child_pension.id, 100_000, "GBP", AS_OF)
    assessment = _assessor(log).assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.household_id), AS_OF))
    assert assessment.current_value.value == 62_000

    unknown = declare_party(log, "person")
    join_household(log, unknown.id, household.household_id)
    blocked = _assessor(log).assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.household_id), AS_OF))
    assert blocked.status == "unavailable"
    assert unknown.id in blocked.limitations[0]


def test_exactly_eighteen_is_an_adult_and_missing_adult_spa_fails_closed(tmp_path):
    log, household, mission = _world(tmp_path)
    adult = declare_party(log, "person")
    join_household(log, adult.id, household.household_id)
    declare_person_date_of_birth(log, adult.id, "2008-08-21", actor="test")
    blocked = _assessor(log).assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.household_id), AS_OF))
    assert blocked.status == "unavailable"
    assert adult.id in blocked.limitations[0]
    assert "State Pension age evidence" in blocked.limitations[0]


def test_person_target_scopes_the_actual_assessment_and_null_target_fails_closed(tmp_path):
    log, household, mission = _world(tmp_path)
    _target(log, household.household_id, mission, household.alex_id)
    result = PensionMissionQueryService(log, household.household_id).evaluate(as_of="2026-08-21T23:00:00Z")
    assert result["mission"]["subject"]["id"] == household.alex_id
    assert result["current_relevant_value"]["value"] == 38_000

    null_log, null_household, null_mission = _world(tmp_path / "null")
    core = EntityProjection(null_log)
    definitions = MissionAssessmentRegistry(); register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(null_log, core, definitions, FinanceTargetMetricResolver())
    descriptor = targets.metric_resolver.describe(null_mission.target_metric)
    from foundry.core import grammar
    grammar.declare(null_log, "core", "mission_target", "legacy-null", {
        "mission_id": null_mission.id, "household_id": null_household.household_id,
        "subject_id": None, "metric_id": null_mission.target_metric,
        "destination_value": 735_000, "destination_unit": descriptor.unit_or_currency,
        "destination_dimension": descriptor.dimension,
        "destination_direction": descriptor.destination_direction, "horizon_kind": "derived",
        "effective_from": AS_OF - 1,
    }, actor="test")
    with pytest.raises(PensionMissionQueryError, match="no canonical subject"):
        PensionMissionQueryService(null_log, null_household.household_id).evaluate(
            as_of="2026-08-21T23:00:00Z")


def test_timing_commands_are_household_bound_exact_and_idempotent(tmp_path):
    log, household, _ = _world(tmp_path)
    service = PensionTimingService(log, household.household_id)
    dob = service.propose_person_date_of_birth(
        person_id=household.alex_id, date_of_birth="1984-01-02", principal="test@example.com")
    first = service.declare_person_date_of_birth(
        person_id=household.alex_id, date_of_birth="1984-01-02", principal="test@example.com",
        proposal_id=dob["proposal_id"], command_id="dob-1")
    assert service.declare_person_date_of_birth(
        person_id=household.alex_id, date_of_birth="1984-01-02", principal="test@example.com",
        proposal_id=dob["proposal_id"], command_id="dob-1") == first
    spa = service.propose_state_pension_age(
        person_id=household.alex_id, state_pension_age=67, effective_at="2026-08-21T00:00:00Z",
        source="DWP forecast", lineage="authorised statement", confidence=.9,
        principal="test@example.com")
    with pytest.raises(PensionTimingError, match="proposal does not match"):
        service.declare_state_pension_age(
            person_id=household.alex_id, state_pension_age=68, effective_at="2026-08-21T00:00:00Z",
            source="DWP forecast", lineage="authorised statement", confidence=.9,
            principal="test@example.com", proposal_id=spa["proposal_id"], command_id="spa-1")
    with pytest.raises(PensionTimingError, match="authorised household"):
        service.propose_person_date_of_birth(person_id="outside", date_of_birth="1980-01-01",
                                              principal="test@example.com")
