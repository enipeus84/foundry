"""Burn 47b: governed mortgage-cover facts and Financial Resilience."""

import time

import pytest

from foundry.core.entities import (
    EntityProjection, declare_mission, declare_party, join_household,
    update_party,
)
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.mission_assessment import (
    MissionAssessmentRegistry, MissionAssessmentRequest,
)
from foundry.core.mission_targets import MissionTargetProjection, TargetQuantity
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mission_targets import FinanceTargetMetricResolver
from foundry.finance.missions import register_finance_mission_definitions
from foundry.finance.resilience_assessment import (
    POLICY_ID, TARGET_METRIC, FinancialResilienceAssessor,
)
from foundry.finance.resilience_evidence import ResilienceEvidenceProjection


def _system(tmp_path, *, reserves=20_280.90, payment=1_701.47):
    as_of = time.time() + 10
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    update_party(log, household.id, {"reporting_currency": "GBP"}, reason="test")
    person = declare_party(log, "person")
    join_household(log, person.id, household.id)
    account = fin.declare_account(log, "checking", "GBP", liquidity_classification="liquid")
    fin.link_ownership(log, "account", account.id, "owner", person.id)
    fin.declare_transaction(log, account.id, reserves, "GBP", "income", as_of - 2)
    mortgage = fin.declare_obligation(log, "mortgage", "GBP", amount=200_000.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", person.id)
    series = fin.declare_recurring_series(
        log, "mortgage_payment", payment, "GBP", cadence="month",
        direction="outflow", essential_category="housing",
        basis="contractual_derived", effective_from=as_of - 2,
        source_reference="lender statement", derivation_reference="promotion",
        settled_obligation_id=mortgage.id)
    mission = declare_mission(
        log, "Mortgage cover", target_metric=TARGET_METRIC,
        assessment_policy_id=POLICY_ID, household_id=household.id)
    core = EntityProjection(log)
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    targets = MissionTargetProjection(
        log, core, definitions, FinanceTargetMetricResolver())
    target = targets.declare(
        household_id=household.id, subject_id=household.id,
        mission_id=mission.id, metric_id=TARGET_METRIC,
        destination=TargetQuantity(18.0, "months", "duration_months"),
        destination_direction="higher_is_better", horizon_kind="none",
        horizon_at=None, effective_from=as_of - 1)
    return log, household, mortgage, series, mission, target, as_of


def _provider(log):
    return FinanceMetricProvider(fin.FinanceEntityProjection(log), EntityProjection(log))


def test_mortgage_commitment_and_runway_use_promoted_series_not_essential_categories(tmp_path):
    log, household, _, _, _, _, as_of = _system(tmp_path)
    provider = _provider(log)
    scope = Subject("party", household.id)
    payment = provider.calculate(MetricRequest("finance.mortgage_commitment_monthly", scope, as_of))
    runway = provider.calculate(MetricRequest("finance.mortgage_payment_runway", scope, as_of))

    assert payment.value == pytest.approx(1_701.47)
    assert payment.calculation_version == "mortgage-commitment-v1"
    assert runway.value == pytest.approx(20_280.90 / 1_701.47)
    assert runway.unit_or_currency == "months"
    assert runway.calculation_version == "mortgage-runway-v1"
    assert provider.calculate(MetricRequest("finance.liquidity_runway", scope, as_of)).status == "unavailable"


def test_mortgage_commitment_selects_current_contract_and_sums_mortgages(tmp_path):
    log, household, _, series, _, _, as_of = _system(tmp_path)
    core = EntityProjection(log)
    person = next(iter(core.members_of(household.id)))
    other = fin.declare_obligation(log, "mortgage", "GBP", amount=50_000.0)
    fin.link_ownership(log, "obligation", other.id, "owes", person.id)
    fin.declare_recurring_series(
        log, "mortgage_payment", 1_600.0, "GBP", cadence="month",
        direction="outflow", essential_category="housing",
        basis="contractual_derived", effective_from=as_of - 1.5,
        source_reference="replacement", derivation_reference="promotion",
        settled_obligation_id=series.settled_obligation_id)
    fin.declare_recurring_series(
        log, "mortgage_payment", 300.0, "GBP", cadence="month",
        direction="outflow", essential_category="housing",
        basis="contractual_declared", effective_from=as_of - 1,
        source_reference="second lender", settled_obligation_id=other.id)
    result = _provider(log).calculate(MetricRequest(
        "finance.mortgage_commitment_monthly", Subject("party", household.id), as_of))

    assert result.value == pytest.approx(1_900.0)
    assert any("2 current mortgage-payment series" in item for item in result.limitations)


def test_mortgage_commitment_rejects_unowned_and_unconvertible_series(tmp_path):
    log, household, mortgage, series, _, _, as_of = _system(tmp_path)
    fin.pause_recurring_series(log, series.id, "replaced for conversion test")
    # A real-looking unowned payment cannot create cover. An owned USD payment
    # with no applicable FX rate remains explicit rather than guessed.
    outsider = fin.declare_obligation(log, "mortgage", "USD", amount=1.0)
    fin.declare_recurring_series(
        log, "mortgage_payment", 1_000.0, "USD", cadence="month",
        direction="outflow", essential_category="housing",
        basis="contractual_declared", effective_from=as_of - 1,
        source_reference="unowned", settled_obligation_id=outsider.id)
    fin.declare_recurring_series(
        log, "mortgage_payment", 1_000.0, "USD", cadence="month",
        direction="outflow", essential_category="housing",
        basis="contractual_declared", effective_from=as_of - 1,
        source_reference="owned USD", settled_obligation_id=mortgage.id)
    result = _provider(log).calculate(MetricRequest(
        "finance.mortgage_commitment_monthly", Subject("party", household.id), as_of))

    assert result.status == "unavailable"
    assert "no valid positive" in result.limitations[0]
    assert "no exchange rate USD->GBP" in result.limitations[1]


def test_assessment_is_available_without_other_essential_categories(tmp_path):
    log, household, _, _, mission, target, as_of = _system(tmp_path)
    core = EntityProjection(log)
    finance = fin.FinanceEntityProjection(log)
    metrics = MetricRegistry()
    metrics.register(FinanceMetricProvider(finance, core))
    targets = MissionTargetProjection(
        log, core, _definitions(), FinanceTargetMetricResolver())
    assessor = FinancialResilienceAssessor(
        metrics, finance, core, ResilienceEvidenceProjection(log), targets)
    result = assessor.assess(MissionAssessmentRequest(
        mission.id, POLICY_ID, Subject("party", household.id), as_of))

    assert set(target.provenance).issubset(result.input_references)
    assert result.current_value.metric_id == TARGET_METRIC
    assert result.current_value.value == pytest.approx(11.92, abs=.01)
    assert result.status == "amber"
    assert result.trajectory_state == "Constrained"
    assert result.mission_margin.state == "Low Margin"
    assert result.current_milestone.label == "Partial Cover"
    assert not result.mission_complete
    assert {item.label for item in result.telemetry} >= {
        "MORTGAGE COVER", "ELIGIBLE LIQUID RESERVES",
        "CANONICAL MONTHLY MORTGAGE PAYMENT", "GOVERNED TARGET COVERAGE",
        "REQUIRED RESERVE", "SURPLUS / SHORTFALL",
    }


def _definitions():
    definitions = MissionAssessmentRegistry()
    register_finance_mission_definitions(definitions)
    return definitions


def test_target_supersession_changes_thresholds_without_code(tmp_path):
    log, household, _, _, mission, target, as_of = _system(tmp_path)
    core = EntityProjection(log)
    targets = MissionTargetProjection(log, core, _definitions(), FinanceTargetMetricResolver())
    targets.declare(
        household_id=household.id, subject_id=household.id,
        mission_id=mission.id, metric_id=TARGET_METRIC,
        destination=TargetQuantity(10.0, "months", "duration_months"),
        destination_direction="higher_is_better", horizon_kind="none",
        horizon_at=None, effective_from=as_of, supersedes=target.id)
    finance = fin.FinanceEntityProjection(log)
    metrics = MetricRegistry(); metrics.register(FinanceMetricProvider(finance, core))
    result = FinancialResilienceAssessor(
        metrics, finance, core, ResilienceEvidenceProjection(log), targets).assess(
            MissionAssessmentRequest(mission.id, POLICY_ID, Subject("party", household.id), as_of + 1))

    assert result.status == "green"
    assert result.mission_complete
