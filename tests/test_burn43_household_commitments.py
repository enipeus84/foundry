"""Burn 43: governed household commitments feed the runway denominator."""

import pytest

from foundry.core.entities import (
    EntityProjection, declare_party, join_household, update_party,
)
from foundry.core.principal_authority import grant_principal_household_authority
from foundry.core.metrics import MetricRequest
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.mortgage_evidence import record_mortgage_evidence
from foundry.application.household_commitments import (
    HouseholdCommitmentDenied, HouseholdCommitmentService,
)


AS_OF = 2_000_000.0


def _system(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    update_party(log, household.id, {"reporting_currency": "GBP"}, reason="test")
    person = declare_party(log, "person")
    join_household(log, person.id, household.id)
    account = fin.declare_account(log, "checking", "GBP", liquidity_classification="liquid")
    fin.link_ownership(log, "account", account.id, "owner", person.id)
    fin.declare_transaction(log, account.id, 12_000.0, "GBP", "income", AS_OF - 10)
    return log, household, account


def _runway(log, household):
    return FinanceMetricProvider(
        fin.FinanceEntityProjection(log), EntityProjection(log)).calculate(
            MetricRequest("finance.liquidity_runway", Subject("party", household.id), AS_OF))


def _na(log, category):
    return fin.declare_recurring_series(
        log, "regular_expense", 0.0, "GBP", cadence="month", direction="outflow",
        essential_category=category, basis="not_applicable", effective_from=AS_OF - 1,
        source_reference=f"policy:{category}")


def test_category_coverage_is_mandatory_and_not_applicable_is_zero(tmp_path):
    log, household, account = _system(tmp_path)
    fin.declare_recurring_series(
        log, "mortgage_payment", 1_000.0, "GBP", cadence="month", direction="outflow",
        essential_category="housing", basis="contractual_declared", effective_from=AS_OF - 1,
        source_reference="mortgage contract", funding_account_id=account.id)
    incomplete = _runway(log, household)
    assert incomplete.status == "unavailable"
    assert "transport" in incomplete.limitations[-1]

    for category in ("transport", "groceries", "childcare", "education", "healthcare", "tax_payment"):
        _na(log, category)
    complete = _runway(log, household)
    assert complete.status == "available"
    assert complete.value == pytest.approx(12.0)


def test_governed_commitment_proposal_executes_idempotently(tmp_path):
    log, household, account = _system(tmp_path)
    grant_principal_household_authority(log, "operator", household.id)
    service = HouseholdCommitmentService(log, "operator", household.id)
    values = {
        "recurring_commitment_type": "regular_expense", "amount": 250.0,
        "currency": "GBP", "cadence": "month", "direction": "outflow",
        "essential_category": "transport", "basis": "operator_estimate",
        "effective_from": AS_OF - 1, "source_reference": "operator estimate 2026-08",
        "funding_account_id": account.id,
    }
    proposed = service.propose(**values)
    executed = service.execute(
        proposal_id=proposed["proposal_id"], command_id="commitment-1", **values)
    replay = service.execute(
        proposal_id=proposed["proposal_id"], command_id="commitment-1", **values)
    series = fin.FinanceEntityProjection(log).recurring_series[executed["series_id"]]
    assert replay == executed
    assert series.basis == "operator_estimate"
    assert series.provenance


def test_cadence_and_fulfilment_prevent_double_counting(tmp_path):
    log, household, account = _system(tmp_path)
    contract = fin.declare_recurring_series(
        log, "mortgage_payment", 1_200.0, "GBP", cadence="year", direction="outflow",
        essential_category="housing", basis="contractual_declared", effective_from=AS_OF - 1,
        source_reference="annual housing contract", funding_account_id=account.id)
    transaction = fin.declare_transaction(
        log, account.id, -1_200.0, "GBP", "housing", AS_OF - 20)
    fin.fulfil(log, transaction.id, contract.id)
    for category in ("transport", "groceries", "childcare", "education", "healthcare", "tax_payment"):
        _na(log, category)
    result = _runway(log, household)
    # £1,200/year = £100/month.  The fulfilled £1,200 observation cannot
    # re-enter residual observed expenditure.
    assert result.value == pytest.approx(108.0)


def test_estimate_is_labelled_and_never_stacks_with_observation(tmp_path):
    log, household, account = _system(tmp_path)
    estimate = fin.declare_recurring_series(
        log, "regular_expense", 400.0, "GBP", cadence="month", direction="outflow",
        essential_category="groceries", basis="operator_estimate", effective_from=AS_OF - 1,
        source_reference="operator declaration", funding_account_id=account.id)
    assert estimate.basis == "operator_estimate"
    fin.declare_transaction(log, account.id, -300.0, "GBP", "groceries", AS_OF - 20)
    for category in ("housing", "transport", "childcare", "education", "healthcare", "tax_payment"):
        _na(log, category)
    provider = FinanceMetricProvider(fin.FinanceEntityProjection(log), EntityProjection(log))
    basis = provider.essential_outflow_basis({next(iter(EntityProjection(log).members_of(household.id))).id}, None, "GBP", AS_OF)
    groceries = next(item for item in basis.categories if item.category == "groceries")
    assert groceries.observed == 300.0
    assert groceries.estimated == 0.0
    assert any("not combined" in item for item in basis.limitations)


def test_mortgage_promotion_retains_lineage_and_stale_proposal_fails_closed(tmp_path):
    log, household, _ = _system(tmp_path)
    person = next(iter(EntityProjection(log).members_of(household.id)))
    mortgage = fin.declare_obligation(log, "mortgage", "GBP", amount=200_000.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", person.id)
    grant_principal_household_authority(log, "operator", household.id)
    first = record_mortgage_evidence(
        log, mortgage.id, "monthly_payment", 1_701.47, AS_OF - 20,
        confidence=.9, source="lender statement", lineage="statement", unit_or_currency="GBP")
    service = HouseholdCommitmentService(log, "operator", household.id)
    proposal = service.propose_mortgage_promotion(mortgage.id, AS_OF)
    record_mortgage_evidence(
        log, mortgage.id, "monthly_payment", 1_750.0, AS_OF - 10,
        confidence=.9, source="lender statement", lineage="revised statement", unit_or_currency="GBP")
    with pytest.raises(HouseholdCommitmentDenied, match="stale"):
        service.execute_mortgage_promotion(
            obligation_id=mortgage.id, as_of=AS_OF,
            proposal_id=proposal["proposal_id"], command_id="promote-1")

    current = service.propose_mortgage_promotion(mortgage.id, AS_OF)
    result = service.execute_mortgage_promotion(
        obligation_id=mortgage.id, as_of=AS_OF,
        proposal_id=current["proposal_id"], command_id="promote-2")
    assert result["amount"] == 1_750.0
    assert result["reference"] != first.event_id
    assert result["derivation"] == result["reference"]

    # A later promotion supersedes by effective date; immutable prior series
    # stays in the log but cannot double the current contractual denominator.
    record_mortgage_evidence(
        log, mortgage.id, "monthly_payment", 1_800.0, AS_OF - 5,
        confidence=.9, source="lender statement", lineage="latest statement", unit_or_currency="GBP")
    replacement = service.propose_mortgage_promotion(mortgage.id, AS_OF)
    service.execute_mortgage_promotion(
        obligation_id=mortgage.id, as_of=AS_OF,
        proposal_id=replacement["proposal_id"], command_id="promote-3")
    provider = FinanceMetricProvider(fin.FinanceEntityProjection(log), EntityProjection(log))
    person_ids = {person.id}
    basis = provider.essential_outflow_basis(person_ids, None, "GBP", AS_OF)
    housing = next(item for item in basis.categories if item.category == "housing")
    assert housing.contractual == 1_800.0
