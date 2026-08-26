"""Burn 30: governed Mortgage Freedom read over the Burn 29 canonical shape."""

from __future__ import annotations

import json
import time

import pytest

from foundry.application.mcp_context import McpPrincipal
from foundry.application.mcp_writes import (
    McpFinancialResourceWrites, McpMortgageEvidenceCapture,
)
from foundry.application.mortgage_mission import (
    MortgageMissionQueryError, MortgageMissionQueryService,
)
from foundry.application.resources import FinancialResourceQuery
from foundry.core import grammar
from foundry.core.entities import (
    EntityProjection, declare_mission, declare_party, join_household, update_party,
)
from foundry.core.metrics import MetricRegistry
from foundry.core.mission_assessment import MissionAssessmentRegistry, MissionAssessmentRequest
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.mortgage_assessment import (
    DAY, POLICY_ID, TARGET_METRIC, MortgageFreedomAssessor,
    MortgageProjectionEngine, _add_calendar_months,
)
from foundry.finance.mortgage_evidence import MortgageEvidenceProjection
from foundry.finance.resilience_evidence import ResilienceEvidenceProjection
from foundry.finance.resilience_metrics import FinanceResilienceMetricProvider
from foundry.mcp_server import create_mcp_server


PRINCIPAL = "mcp@example.com"
#: Burn 29's real canonical dates, so derived contractual maturity is the
#: production value (1 June 2050) rather than a relative fixture artefact.
NOW = 1_787_616_000.0            # 2026-08-25T00:00:00Z
MORTGAGE_START = 1_748_736_000.0  # 2025-06-01T00:00:00Z
FIXED_RATE_EXPIRY = 1_816_992_000.0  # 2027-07-31T00:00:00Z
ORIGINAL_TERM_MONTHS = 300
_DEFAULT_TARGET_DATE = object()

#: The twelve fields Burn 29 made canonical, at their production values.
BURN29_EVIDENCE: dict[str, object] = {
    "property_role": "primary_residence",
    "lender": "National Westminster Bank Plc",
    "original_advance": 311_495.00,
    "mortgage_start": MORTGAGE_START,
    "balance": 241_728.15,
    "repayment_type": "capital_repayment",
    "interest_type": "fixed",
    "interest_rate": .0433,
    "monthly_payment": 1_701.47,
    "original_term_months": float(ORIGINAL_TERM_MONTHS),
    "remaining_term_months": 200.0,
    "fixed_rate_expiry": FIXED_RATE_EXPIRY,
}

_CURRENCY_FIELDS = {"original_advance", "balance", "monthly_payment"}


def _burn29_world(tmp_path, *, evidence_fields=None, valuation=None):
    """Rebuild the Burn 29 canonical shape through the governed write path."""
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    christopher = declare_party(log, "person")
    fiona = declare_party(log, "person")
    update_party(log, christopher.id, {"name": "Christopher"}, "test identity")
    update_party(log, fiona.id, {"name": "Fiona"}, "test identity")
    join_household(log, christopher.id, household.id)
    join_household(log, fiona.id, household.id)
    grant_principal_household_authority(log, PRINCIPAL, household.id, actor="test")

    writes = McpFinancialResourceWrites(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    home = writes.create(
        resource_type="property", currency="GBP", name="Tomcroy House",
        owners=["Christopher", "Fiona"], command_id="property-create",
        proposal_id=writes.propose_create(
            resource_type="property", currency="GBP", name="Tomcroy House",
            owners=["Christopher", "Fiona"]).proposal_id)
    mortgage = writes.create(
        resource_type="mortgage", currency="GBP", name="Home mortgage",
        owners=["Christopher", "Fiona"], secured_property_id=home["id"],
        command_id="mortgage-create",
        proposal_id=writes.propose_create(
            resource_type="mortgage", currency="GBP", name="Home mortgage",
            owners=["Christopher", "Fiona"], secured_property_id=home["id"]).proposal_id)

    capture = McpMortgageEvidenceCapture(log, PRINCIPAL, household.id, "claude-code", "gpt-test")
    fields = dict(BURN29_EVIDENCE if evidence_fields is None else evidence_fields)
    if valuation is not None:
        fields["property_valuation"] = valuation
        fields["valuation_basis"] = "index_estimate"
    for index, (field, value) in enumerate(fields.items()):
        values = dict(
            obligation_id=mortgage["id"], field=field, value=value,
            effective_at=NOW - 10 * DAY, confidence=.95,
            source="National Westminster Bank Plc statement",
            lineage="household supplied", unit_or_currency=(
                "GBP" if field in _CURRENCY_FIELDS or field == "property_valuation" else None))
        receipt = capture.propose(**values)
        capture.execute(**values, proposal_id=receipt.proposal_id,
                        command_id=f"evidence-{index}")
    return log, household, home, mortgage


def _declare_mortgage_mission(log, household, *, assumption_set_id=None,
                              target_value=0.0, target_date=_DEFAULT_TARGET_DATE,
                              declare_target=True):
    contractual_maturity = _add_calendar_months(
        MORTGAGE_START, ORIGINAL_TERM_MONTHS)
    mission = declare_mission(
        log, "Mortgage free by contractual term",
        target_metric=TARGET_METRIC, target_value=target_value,
        target_date=(contractual_maturity if target_date is _DEFAULT_TARGET_DATE
                     else target_date),
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumption_set_id,
        household_id=household.id)
    if declare_target:
        definitions = MissionAssessmentRegistry()
        register_finance_mission_definitions(definitions)
        targets = MissionTargetProjection(
            log, EntityProjection(log), definitions, FinanceTargetMetricResolver())
        targets.declare(
            household_id=household.id, subject_id=household.id,
            mission_id=mission.id, metric_id=TARGET_METRIC,
            destination=TargetQuantity(0.0, "GBP", "currency"),
            destination_direction="lower_is_better", horizon_kind="by_date",
            horizon_at=contractual_maturity,
            effective_from=log.get(mission.provenance[0])["ts"])
    return mission


def _assumptions(log):
    return finance.declare_assumption_set(
        log, "Mortgage Freedom baseline", "v1", {
            "low_post_fix_rate": .0333,
            "base_post_fix_rate": .0433,
            "high_post_fix_rate": .0533,
            "forecast_horizon_months": 480.0,
            "balance_stale_after_days": 120.0,
            "valuation_stale_after_days": 365.0,
            "liquidity_floor_months": 12.0,
        })


def _service(log, household):
    return MortgageMissionQueryService(log, household.id)


def _direct_assessment(log, household, mission):
    """The unchanged application/domain read the MCP surface must mirror."""
    core, fin = EntityProjection(log), FinanceEntityProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(fin, core))
    metrics.register(FinanceResilienceMetricProvider(
        fin, core, ResilienceEvidenceProjection(log)))
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(
        log, core, definitions, FinanceTargetMetricResolver())
    assessor = MortgageFreedomAssessor(
        fin, core, metrics, MortgageEvidenceProjection(log), targets)
    return assessor.assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.id), time.time()))


def _production_shaped_target(log, household, mission):
    """Replay the deployed legacy declaration shape: null subject and basis."""
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(
        log, EntityProjection(log), definitions, FinanceTargetMetricResolver())
    predecessor = targets.in_force(mission.id, time.time())
    assert predecessor is not None
    target_id = grammar.new_id()
    grammar.declare(log, "core", "mission_target", target_id, {
        "entity_id": target_id,
        "mission_id": mission.id,
        "household_id": household.id,
        "subject_id": None,
        "metric_id": TARGET_METRIC,
        "destination_value": 0.0,
        "destination_unit": "GBP",
        "destination_dimension": "currency",
        "destination_direction": "lower_is_better",
        "horizon_kind": "by_date",
        "horizon_at": 2_312_755_200.0,  # 2043-04-16
        "effective_from": predecessor.effective_from,
        "supersedes": predecessor.id,
    })
    return target_id


def _tool(server, name):
    return server._tool_manager.get_tool(name).fn


# ------------------------------------------------------------------ read-only

def test_read_is_registered_and_never_mutates_canonical_state(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)
    server = create_mcp_server(
        FinancialResourceQuery(log, household.id),
        McpPrincipal(PRINCIPAL, household.id, "claude-code", "gpt-test"))
    before = list(log.events())

    result = _tool(server, "inspect_mortgage_freedom")()

    assert list(log.events()) == before
    json.dumps(result)
    assert result["policy_id"] == POLICY_ID
    assert result["subject"] == {"kind": "party", "id": household.id}


def test_repeated_reads_are_side_effect_free(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)
    service = _service(log, household)
    first = service.inspect(as_of="2026-08-25T00:00:00Z")
    before = list(log.events())

    second = service.inspect(as_of="2026-08-25T00:00:00Z")

    assert list(log.events()) == before
    assert first == second


# ------------------------------------------------------------------ dependencies

def test_absent_mission_is_reported_not_manufactured(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)

    result = _service(log, household).inspect()

    assert result["mission"] is None
    assert result["mission_state"] == "not_declared"
    assert result["completeness"] == "unavailable"
    assert result["evaluable"] is False
    assert result["blockers"] == ["Mortgage Freedom Mission is not declared"]
    assert result["target"]["state"] == "not_applicable"
    assert result["assumption_set"]["state"] == "not_applicable"
    assert not any(event["kind"] == "core.mission.declared" for event in log.events())


def test_absent_assumption_set_is_named_as_the_exact_dependency(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    _declare_mortgage_mission(log, household)

    result = _service(log, household).inspect()

    assert result["mission"] is not None
    assert result["assumption_set"] == {
        "state": "absent", "reason": "Mission declares no Assumption Set"}
    assert result["completeness"] == "unavailable"
    assert result["blockers"] == ["active Assumption Set not found"]


def test_production_shaped_target_reaches_assumption_set_blocker(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    mission = _declare_mortgage_mission(
        log, household, target_value=None, target_date=None)
    declaration = next(event for event in log.events()
                       if event["id"] == mission.provenance[0])
    assert declaration["payload"]["target_value"] is None
    assert declaration["payload"]["target_date"] is None
    target_id = _production_shaped_target(log, household, mission)

    # Projection state is the production shape: no Assumption Set and a
    # legacy Target with unspecified subject and no basis.
    result = _service(log, household).inspect()

    assert result["target"]["id"] == target_id
    assert result["target"]["subject_id"] is None
    assert result["target"]["basis"] is None
    assert result["target"]["horizon_at"].startswith("2043-04-16")
    assert result["contractual_maturity_at"] is None
    assert result["blockers"] == ["active Assumption Set not found"]


def test_in_force_mission_target_authorises_the_assessment(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id)

    result = _service(log, household).inspect()

    assert result["target"]["state"] == "in_force"
    assert result["target"]["destination"]["value"] == 0.0
    assert result["mission"]["id"] == mission.id
    assert result["completeness"] == "complete"


def test_missing_property_valuation_is_the_reported_blocker(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)

    result = _service(log, household).inspect()

    assert result["completeness"] == "unavailable"
    assert result["blockers"] == ["no eligible secured-property valuation was found"]
    assert result["current_position"] is None
    assert result["forecast"] is None


def test_missing_mortgage_evidence_names_the_missing_fields(tmp_path):
    partial = {field: value for field, value in BURN29_EVIDENCE.items()
               if field not in {"interest_rate", "monthly_payment"}}
    log, household, _, _ = _burn29_world(
        tmp_path, evidence_fields=partial, valuation=436_638.42)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)

    result = _service(log, household).inspect()

    assert result["completeness"] == "unavailable"
    assert result["blockers"][0].startswith("Mortgage evidence missing:")


# ------------------------------------------------------------------ fidelity

def test_complete_read_mirrors_the_direct_domain_assessment(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id)
    assessment = _direct_assessment(log, household, mission)
    assert assessment.completeness == "complete"

    result = _service(log, household).inspect()

    assert result["completeness"] == assessment.completeness
    assert result["assessment_status"] == assessment.status
    assert result["mission_complete"] == assessment.mission_complete
    assert result["confidence"]["state"] == assessment.confidence.state
    assert result["blockers"] == []
    balance = result["current_position"]["mortgage_balance"]
    assert balance["value"] == BURN29_EVIDENCE["balance"]
    assert balance["metric_id"] == TARGET_METRIC
    equity = result["current_position"]["finance.property_current_equity"]
    assert equity["value"] == pytest.approx(436_638.42 - 241_728.15)
    ltv = result["current_position"]["finance.mortgage_ltv"]
    assert ltv["value"] == pytest.approx(241_728.15 / 436_638.42)
    assert result["contractual_maturity_at"].startswith("2050-06-01")
    assert result["forecast"]["estimated_payoff_at"] is not None
    assert result["delta_v"] is not None
    assert result["mission_margin"] is not None


def test_forecast_failure_preserves_present_state_outputs(tmp_path, monkeypatch):
    """A downstream projection failure must not erase valid current-state truth.

    The projection engine cannot be driven to failure through evidence alone,
    so the failure is injected: what is under test is that the read serializes
    the assessor's ``partial`` result faithfully, not the engine's own limits.
    """
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    mission = _declare_mortgage_mission(
        log, household, assumption_set_id=_assumptions(log).id)

    def _fail(*args, **kwargs):
        raise ValueError("forecast is unavailable")

    monkeypatch.setattr(MortgageProjectionEngine, "project", _fail)
    assessment = _direct_assessment(log, household, mission)
    assert assessment.completeness == "partial"

    result = _service(log, household).inspect()

    assert result["completeness"] == "partial"
    assert result["evaluable"] is False
    assert result["blockers"] and result["blockers"][0]
    assert result["current_position"]["finance.property_current_equity"]["value"] \
        == pytest.approx(436_638.42 - 241_728.15)
    assert result["current_position"]["finance.mortgage_ltv"]["value"] \
        == pytest.approx(241_728.15 / 436_638.42)


# ------------------------------------------------------------------ scope

def test_another_households_mission_id_is_refused_and_leaks_nothing(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    _declare_mortgage_mission(log, household, assumption_set_id=_assumptions(log).id)
    other_household = declare_party(log, "household")
    other_mission = declare_mission(
        log, "Other household mortgage", target_metric=TARGET_METRIC,
        target_value=0.0, target_date=NOW + 1000 * DAY,
        assessment_policy_id=POLICY_ID, household_id=other_household.id)

    with pytest.raises(MortgageMissionQueryError) as excinfo:
        _service(log, household).inspect(other_mission.id)

    assert "not authorised for this household" in str(excinfo.value)
    assert other_mission.id not in str(excinfo.value)
    assert "Other household mortgage" not in str(excinfo.value)


def test_household_without_its_own_mission_does_not_see_another(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path, valuation=436_638.42)
    other_household = declare_party(log, "household")
    declare_mission(
        log, "Other household mortgage", target_metric=TARGET_METRIC,
        target_value=0.0, target_date=NOW + 1000 * DAY,
        assessment_policy_id=POLICY_ID, household_id=other_household.id)

    result = _service(log, household).inspect()

    assert result["mission"] is None
    assert result["mission_state"] == "not_authorised_for_household"
    assert result["subject"]["id"] == household.id


def test_invalid_as_of_is_refused(tmp_path):
    log, household, _, _ = _burn29_world(tmp_path)
    with pytest.raises(MortgageMissionQueryError, match="ISO-8601"):
        _service(log, household).inspect(as_of="not-a-timestamp")
    with pytest.raises(MortgageMissionQueryError, match="timezone"):
        _service(log, household).inspect(as_of="2026-08-25T00:00:00")
