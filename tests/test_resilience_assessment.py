"""RFC-008 Financial Resilience mission assessment."""

import ast
import inspect

import pytest

from foundry.core.entities import EntityProjection, declare_mission
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.mission_assessment import (
    MissionAssessmentRegistry,
    MissionAssessmentRequest,
)
from foundry.core.scope import Subject
from foundry.demo_data import build_morgan_household, _seed_transactions
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.resilience_assessment import (
    APPLICABILITY,
    CALCULATION_VERSION,
    POLICY_ID,
    TARGET_METRIC,
    FinancialResilienceAssessor,
    FinancialResilienceInputs,
    FinancialResiliencePolicy,
)
from foundry.finance.resilience_evidence import (
    ResilienceEvidenceProjection,
    record_resilience_evidence,
)
from foundry.finance.resilience_metrics import (
    FinanceResilienceMetricProvider,
)


AS_OF = 1_785_170_000.0
DAY = 86_400.0


def _declare_policy(log):
    return fin.declare_assumption_set(
        log,
        "Financial Resilience policy",
        "v1",
        {
            "reserve_target_months": 18.0,
            "secure_floor_months": 6.0,
            "critical_floor_months": 1.0,
            "income_concentration_limit": .5,
            "commitment_horizon_months": 12.0,
            "outflow_crosscheck_tolerance": .2,
            "evidence_stale_after_days": 120.0,
            "movement_lookback_days": 90.0,
            "income_reduction_fraction": .25,
            "income_reduction_months": 3.0,
            "unexpected_expenditure": 5_000.0,
            "rate_shock_monthly_cost": 300.0,
            "temporary_unemployment_months": 3.0,
        },
        actor="synthetic_demo",
    )


def _record(
    log,
    party_id,
    field,
    value,
    *,
    confidence=.9,
    effective_at=AS_OF,
    due_at=None,
    description="",
    source="synthetic household declaration",
):
    return record_resilience_evidence(
        log,
        party_id,
        field,
        value,
        effective_at,
        confidence=confidence,
        source=source,
        lineage="synthetic RFC-008 assessment evidence",
        unit_or_currency=(
            None if field == "protection_declaration" else "GBP"),
        due_at=due_at,
        description=description,
        actor="synthetic_demo",
    )


def _seed(
    tmp_path,
    *,
    income_sources=2,
    commitment=True,
    confidence=.9,
    future=False,
    invalid=False,
    protection=False,
):
    log = EventLog(tmp_path / "events.jsonl")
    household = build_morgan_household(log, as_of=AS_OF)
    _seed_transactions(log, household, AS_OF)
    assumptions = _declare_policy(log)
    fin.declare_scenario(
        log,
        "Maintain a £250 monthly emergency-reserve contribution",
        assumptions.id,
        {"monthly_reserve_contribution": 250.0},
        action_type="maintain_reserve_contribution",
        action_label="Maintain reserve contribution",
        unit_or_currency="GBP",
        cadence="month",
        actor="synthetic_demo",
    )
    mission = declare_mission(
        log,
        "Financial Resilience — 18 months and protections",
        target_metric=TARGET_METRIC,
        target_value=18.0,
        assessment_policy_id=POLICY_ID,
        assumption_set_id=assumptions.id,
        actor="synthetic_demo",
    )
    for index in range(income_sources):
        _record(
            log,
            household.household_id,
            "income_source_monthly",
            4_000.0 - index * 500.0,
            confidence=confidence,
            description=f"declared income source {index + 1}",
            source=f"declared income source {index + 1}",
        )
    if commitment:
        _record(
            log,
            household.household_id,
            "near_term_commitment",
            2_000.0,
            confidence=confidence,
            due_at=AS_OF + 30 * DAY,
            description="annual insurance premium",
        )
    if future:
        _record(
            log,
            household.household_id,
            "income_source_monthly",
            10_000.0,
            effective_at=AS_OF + 30 * DAY,
            description="future income declaration",
        )
    if protection:
        _record(
            log,
            household.household_id,
            "protection_declaration",
            "<script>claims protection</script>",
            description="<b>must remain unscored</b>",
        )
    if invalid:
        log.append("finance.resilience_evidence.recorded", {
            "party_id": household.household_id,
            "field": "__class__",
            "value": "<script>",
            "effective_at": AS_OF,
            "confidence": "trusted",
            "source": {"forged": True},
            "lineage": [],
        })
    return log, household, assumptions, mission


def _assessment(
    log,
    household,
    mission,
    *,
    concentration_available=True,
):
    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    if not concentration_available:
        finance.positions.clear()
    evidence = ResilienceEvidenceProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(finance, core))
    metrics.register(FinanceResilienceMetricProvider(
        finance, core, evidence))
    assessor = FinancialResilienceAssessor(
        metrics, finance, core, evidence)
    registry = MissionAssessmentRegistry()
    register_finance_mission_definitions(registry)
    registry.register(assessor)
    request = MissionAssessmentRequest(
        mission.id,
        POLICY_ID,
        Subject("party", household.household_id),
        AS_OF,
    )
    return registry.dispatch(request), assessor, metrics, core


def test_steady_state_shape_and_applicability_are_exact(tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert result.status != "unavailable"
    assert result.calculation_version == CALCULATION_VERSION
    assert result.applicability == APPLICABILITY
    assert result.eta is None
    assert result.delta_v is None
    assert result.forecast == ()
    assert result.trajectory == ()
    assert result.current_value.metric_id == "finance.liquidity_runway"
    assert result.current_value.unit_or_currency == "months"
    assert all(
        "probability" not in item.label.lower()
        for item in result.telemetry
    )


def test_reserve_bands_and_completion_destination_are_frozen(tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert [milestone.label for milestone in result.milestones] == [
        "Exposed", "Fragile", "Buffered", "Secure", "Fortified",
    ]
    assert [
        (milestone.lower_bound, milestone.upper_bound)
        for milestone in result.milestones
    ] == [
        (0.0, 1.0),
        (1.0, 3.0),
        (3.0, 6.0),
        (6.0, 18.0),
        (18.0, None),
    ]
    assert sum(milestone.is_current for milestone in result.milestones) == 1
    assert result.current_milestone.label == "Fortified"
    assert result.mission_complete
    assert [
        milestone.label for milestone in result.milestones
        if milestone.completes_mission
    ] == ["Fortified"]
    assert not next(
        item for item in result.milestones
        if item.label == "Secure").completes_mission


def test_dispatch_accepts_provider_direction_and_unique_milestone_envelope(
        tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert result.status == "green"
    assert result.limitations != (
        "assessment provider failed safely",)
    assert all(
        milestone.destination_direction == "higher_is_better"
        for milestone in result.milestones
    )
    assert len({item.id for item in result.milestones}) == 5
    assert len({item.order for item in result.milestones}) == 5


def test_worst_factor_wins_without_policy_weights(tmp_path):
    good_log, good_household, _, good_mission = _seed(
        tmp_path / "good")
    weaker_log, weaker_household, _, weaker_mission = _seed(
        tmp_path / "weaker", income_sources=1)

    good, _, _, _ = _assessment(
        good_log, good_household, good_mission)
    weaker, _, _, _ = _assessment(
        weaker_log, weaker_household, weaker_mission)

    assert good.mission_margin.state == "High Margin"
    assert weaker.mission_margin.state == "Adequate Margin"
    assert "income concentration band 2" \
        in weaker.mission_margin.description
    fields = FinancialResilienceInputs.__dataclass_fields__
    assert not any(
        "weight" in field.lower() or "coefficient" in field.lower()
        for field in fields
    )
    factor_labels = {
        "RESERVE COVERAGE",
        "INCOME CONCENTRATION",
        "COMMITMENT COVERAGE",
        "OBLIGATION HEADROOM",
    }
    assert factor_labels <= {item.label for item in good.telemetry}
    assert all(
        "BAND " in item.qualifier
        for item in good.telemetry
        if item.label in factor_labels
    )


def test_income_source_restatement_does_not_fabricate_plurality(tmp_path):
    log, household, _, mission = _seed(
        tmp_path, income_sources=1)
    baseline, _, _, _ = _assessment(log, household, mission)
    _record(
        log,
        household.household_id,
        "income_source_monthly",
        3_800.0,
        effective_at=AS_OF + 1.0,
        description="corrected declared income source 1",
        source="declared income source 1",
    )

    corrected, _, _, _ = _assessment(log, household, mission)
    income_item = next(
        item for item in corrected.telemetry
        if item.label == "INCOME CONCENTRATION")

    assert "1 DECLARED SOURCE(S)" in income_item.qualifier
    assert corrected.mission_margin.state == baseline.mission_margin.state
    assert corrected.trajectory_state == baseline.trajectory_state


def test_supported_confidence_cap_and_protection_absence_are_visible(tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert result.confidence.state == "Supported"
    assert result.confidence.state != "Established"
    assert "Established is unavailable" in result.confidence.basis
    assert any(
        "Protection and insurance are not assessed" in limitation
        and "capped at Supported" in limitation
        for limitation in result.limitations
    )
    rendered_language = " ".join((
        result.confidence.basis,
        result.confidence_basis,
        *result.limitations,
    )).lower()
    assert "not assessed" in rendered_language
    assert "unprotected" not in rendered_language


@pytest.mark.parametrize("changes,expected", [
    ({"income_sources": 0}, "Income-source evidence is excluded."),
    ({"commitment": False}, "Near-term commitment evidence is excluded."),
    ({"confidence": .7}, "provisional confidence"),
    ({"future": True}, "Future-dated resilience evidence exists"),
    ({"invalid": True}, "Malformed resilience evidence is quarantined"),
])
def test_optional_evidence_degrades_honestly(
        tmp_path, changes, expected):
    log, household, _, mission = _seed(tmp_path, **changes)

    result, _, _, _ = _assessment(log, household, mission)

    assert result.status != "unavailable"
    assert result.confidence.state == "Provisional"
    combined = " ".join((
        result.confidence.basis,
        *result.limitations,
    ))
    assert expected in combined


def test_protection_declaration_is_reserved_and_never_scored(tmp_path):
    baseline_log, baseline_household, _, baseline_mission = _seed(
        tmp_path / "baseline")
    declared_log, declared_household, _, declared_mission = _seed(
        tmp_path / "declared", protection=True)

    baseline, _, _, _ = _assessment(
        baseline_log, baseline_household, baseline_mission)
    declared, _, _, _ = _assessment(
        declared_log, declared_household, declared_mission)

    assert declared.status == baseline.status
    assert declared.trajectory_state == baseline.trajectory_state
    assert declared.mission_margin == baseline.mission_margin
    assert declared.confidence == baseline.confidence
    assert declared.mission_complete == baseline.mission_complete
    combined = " ".join(declared.limitations).lower()
    assert "unprotected" not in combined
    assert "claims protection" not in combined


def test_stresses_are_telemetry_not_forecasts_or_scenarios(tmp_path):
    log, household, _, mission = _seed(tmp_path)
    before = len(FinanceEntityProjection(log).scenarios)

    result, _, _, _ = _assessment(log, household, mission)
    after = len(FinanceEntityProjection(log).scenarios)
    stresses = tuple(
        item for item in result.telemetry
        if "DETERMINISTIC STRESS" in item.qualifier)

    assert len(stresses) == 4
    assert all(item.result.unit_or_currency == "months"
               for item in stresses)
    assert all("NOT A PROBABILITY" in item.qualifier
               for item in stresses)
    values = {item.result.metric_id: item.result.value for item in stresses}
    runway = result.current_value.value
    assert values[
        "finance.resilience_stress_income_reduction"
    ] == pytest.approx(runway)
    assert values[
        "finance.resilience_stress_unexpected_expenditure"
    ] < runway
    assert values["finance.resilience_stress_rate_shock"] < runway
    assert values[
        "finance.resilience_stress_temporary_unemployment"
    ] == pytest.approx(max(0.0, runway - 3.0))
    assert result.forecast == ()
    assert before == after == 1
    scenario_names = {
        scenario.name for scenario in
        FinanceEntityProjection(log).scenarios.values()
    }
    assert not any("stress" in name.lower() for name in scenario_names)


def test_income_reduction_stress_is_omitted_without_income_evidence(
        tmp_path):
    log, household, _, mission = _seed(
        tmp_path, income_sources=0)

    result, _, _, _ = _assessment(log, household, mission)
    stress_ids = {
        item.result.metric_id for item in result.telemetry
        if "DETERMINISTIC STRESS" in item.qualifier
    }

    assert "finance.resilience_stress_income_reduction" not in stress_ids
    assert len(stress_ids) == 3
    assert any(
        "Income-reduction stress is excluded" in limitation
        for limitation in result.limitations
    )


def test_income_stress_survives_unavailable_concentration_without_false_copy(
        tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(
        log,
        household,
        mission,
        concentration_available=False,
    )
    stress_ids = {
        item.result.metric_id for item in result.telemetry
        if "DETERMINISTIC STRESS" in item.qualifier
    }

    assert "finance.resilience_stress_income_reduction" in stress_ids
    assert not any(
        "Income-reduction stress is excluded" in limitation
        for limitation in result.limitations
    )
    assert any(
        "employer-concentration evidence is not available" in limitation
        for limitation in result.limitations
    )
    assert "income concentration" not in result.mission_margin.description
    assert result.confidence.state == "Provisional"


def test_net_negative_runway_remains_exposed_and_critical(tmp_path):
    log, household, _, mission = _seed(tmp_path)
    fin.declare_transaction(
        log,
        household.joint_checking_id,
        -1_000_000.0,
        "GBP",
        "discretionary",
        AS_OF,
        description="net-negative liquid-balance fixture",
    )

    result, _, _, _ = _assessment(log, household, mission)

    assert result.status == "red"
    assert result.current_value.value < 0
    assert result.current_milestone.label == "Exposed"
    assert result.trajectory_state == "Critical"
    assert result.mission_margin.state == "Negative Margin"
    assert result.milestones
    assert result.current_value.input_references
    assert "assessment provider failed safely" not in result.limitations


def test_completion_reopens_at_sixteen_months_without_event_append(tmp_path):
    log, household, assumptions, mission = _seed(tmp_path)
    complete, _, metrics, core = _assessment(log, household, mission)
    scope = Subject("party", household.household_id)
    outflow = metrics.dispatch(MetricRequest(
        "finance.essential_outflow_monthly",
        scope,
        AS_OF,
        assumption_set_id=assumptions.id,
    ))
    target = metrics.dispatch(MetricRequest(
        "finance.emergency_reserve_target",
        scope,
        AS_OF,
        assumption_set_id=assumptions.id,
    ))
    gap = metrics.dispatch(MetricRequest(
        "finance.emergency_reserve_gap",
        scope,
        AS_OF,
        assumption_set_id=assumptions.id,
    ))
    liquid = target.value - gap.value
    reduction = liquid - 16.0 * outflow.value
    fin.declare_transaction(
        log,
        household.joint_checking_id,
        -reduction,
        "GBP",
        "discretionary",
        AS_OF,
        description="reversible completion test",
    )
    before = (tmp_path / "events.jsonl").read_bytes()

    reopened, _, _, reopened_core = _assessment(
        log, household, mission)

    assert complete.mission_complete
    assert complete.current_milestone.label == "Fortified"
    assert not reopened.mission_complete
    assert reopened.current_value.value == pytest.approx(16.0)
    assert reopened.current_milestone.label == "Secure"
    assert reopened.trajectory_state == "Constrained"
    assert reopened.mission_margin.state == "Adequate Margin"
    assert reopened.status == "amber"
    assert reopened_core.missions[mission.id].status == "active"
    assert core.missions[mission.id].status == "active"
    assert (tmp_path / "events.jsonl").read_bytes() == before


def test_recommendation_exposes_constraint_without_delta_v(tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert len(result.recommendations) == 1
    recommendation = result.recommendations[0]
    assert recommendation.action_label == "Maintain reserve contribution"
    assert recommendation.amount == 250.0
    assert recommendation.cadence == "month"
    assert "current liquidity runway is" in recommendation.action
    assert "declared 18-month reserve destination" in recommendation.action
    assert "Preserve the full reserve" in recommendation.action
    assert recommendation.evidence_references
    assert recommendation.assumption_references
    assert recommendation.estimated_delta_v_days is None
    assert recommendation.estimated_delta_v_months is None
    assert recommendation.delta_v_direction is None
    assert result.delta_v is None


def test_available_telemetry_has_lineage_and_policy_references(tmp_path):
    log, household, _, mission = _seed(tmp_path)

    result, _, _, _ = _assessment(log, household, mission)

    assert result.assumption_references
    for item in result.telemetry:
        if item.result.status == "available":
            assert item.result.input_references, item.label
    policy_telemetry = tuple(
        item for item in result.telemetry
        if item.label != "RESERVE COVERAGE")
    assert all(
        item.result.assumption_references
        for item in policy_telemetry
    )


def test_assessment_is_deterministic_independent_and_read_only(tmp_path):
    log, household, _, mission = _seed(tmp_path)
    before = (tmp_path / "events.jsonl").read_bytes()

    first, assessor, _, _ = _assessment(log, household, mission)
    second, _, _, _ = _assessment(log, household, mission)

    assert first == second
    assert assessor.owned_policy_ids() == {POLICY_ID}
    assert (tmp_path / "events.jsonl").read_bytes() == before


def test_assessor_has_no_registry_or_assessor_dependency_and_no_hidden_inference():
    import foundry.finance.resilience_assessment as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    names = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    assert "MissionAssessmentRegistry" not in names
    assert not any(
        module_name.startswith("foundry.finance")
        and module_name.endswith((
            ".mission_assessment",
            ".mortgage_assessment",
        ))
        for module_name in imports
    )
    for forbidden in (
        "transaction.description",
        "account.name",
        "series.description",
        "RecurringSeries",
        "protection_declaration\" in",
        "unprotected",
    ):
        assert forbidden not in source
    assert "APPLICABILITY" in source
    assert "if not result.eta" not in source
    assert "if not result.trajectory" not in source


def test_policy_has_no_static_archetype_or_weight_coefficients():
    fields = FinancialResiliencePolicy.__dataclass_fields__

    assert fields["destination_months"].default == 18.0
    assert "archetype" not in fields
    assert not any("weight" in name for name in fields)
