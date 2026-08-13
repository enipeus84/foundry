"""RFC-009 P1-P7 metric definitions and non-duplication rules."""

import pytest

from foundry.core.entities import (
    EntityProjection,
    declare_party,
    join_household,
    update_party,
)
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.pension_evidence import (
    PensionEvidenceProjection,
    record_pension_evidence,
)
from foundry.finance.pension_metrics import FinancePensionMetricProvider


AS_OF = 1_800_000_000.0


def _net_worth(log, scope, as_of=AS_OF):
    return FinanceMetricProvider(
        FinanceEntityProjection(log), EntityProjection(log)).calculate(
            MetricRequest("finance.net_worth", scope, as_of))


def _pension_wealth(log, scope, assumption_set_id, as_of=AS_OF):
    return FinancePensionMetricProvider(
        FinanceEntityProjection(log), EntityProjection(log),
        PensionEvidenceProjection(log)).calculate(MetricRequest(
            "finance.pension_wealth", scope, as_of,
            assumption_set_id=assumption_set_id))


def _record(log, subject_id, field, value, *, at=AS_OF, unit="GBP"):
    return record_pension_evidence(
        log,
        subject_id,
        field,
        value,
        at,
        confidence=.9,
        source="synthetic statement",
        lineage="RFC-009 metric fixture",
        unit_or_currency=unit,
        actor="synthetic_demo",
    )


def _fixture(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household = declare_party(log, "household")
    update_party(
        log,
        household.id,
        {"reporting_currency": "GBP"},
        "test reporting currency",
    )
    first = declare_party(log, "person")
    second = declare_party(log, "person")
    join_household(log, first.id, household.id)
    join_household(log, second.id, household.id)

    first_pension = fin.declare_account(
        log, "pension", "GBP", tax_wrapper="pension_wrapper",
        liquidity_classification="illiquid_long")
    second_pension = fin.declare_account(
        log, "pension", "GBP", tax_wrapper="pension_wrapper",
        liquidity_classification="illiquid_long")
    fin.link_ownership(log, "account", first_pension.id, "owner", first.id)
    fin.link_ownership(log, "account", second_pension.id, "owner", second.id)
    fin.declare_valuation(
        log, first_pension.id, 40_000.0, "GBP", AS_OF - 10)
    fin.declare_valuation(
        log, second_pension.id, 22_000.0, "GBP", AS_OF - 10)

    assumptions = fin.declare_assumption_set(
        log, "Pension Independence", "v1", {
            "required_retirement_income_annual": 40_000.0,
            "low_real_return": .01,
            "base_real_return": .03,
            "high_real_return": .05,
            "sustainable_withdrawal_rate": .04,
            "assumed_annual_fee_percent": .0075,
            "contribution_stale_after_days": 400.0,
            "valuation_stale_after_days": 550.0,
            "evidence_crosscheck_tolerance": .20,
            "accelerated_threshold_months": 12.0,
            "divergent_floor_fraction": .75,
            "surplus_high_fraction": .20,
            "shortfall_low_fraction": .10,
            "sp_reliance_low_fraction": 1 / 3,
            "sp_reliance_mid_fraction": .5,
            "sp_reliance_high_fraction": 2 / 3,
            "delta_v_lookback_days": 90.0,
            "recommendation_liquidity_floor_months": 6.0,
        })

    for account_id, employee, employer in (
        (first_pension.id, 4_000.0, 3_000.0),
        (second_pension.id, 2_000.0, 1_500.0),
    ):
        _record(log, account_id, "employee_contribution_annual", employee)
        _record(log, account_id, "employer_contribution_annual", employer)
        _record(log, account_id, "annual_fee_percent", .006, unit="fraction")
        _record(
            log, account_id, "contribution_payment_employee",
            employee / 12, at=AS_OF - 20 * 86_400)
        _record(
            log, account_id, "contribution_payment_employer",
            employer / 12, at=AS_OF - 20 * 86_400)

    for person_id, annual, age in (
        (first.id, 6_000.0, 67.0),
        (second.id, 4_600.0, 68.0),
    ):
        _record(log, person_id, "state_pension_annual", annual)
        _record(log, person_id, "state_pension_age", age, unit="years")
        _record(
            log, person_id, "state_pension_basis", "accrued_to_date",
            unit=None)

    jurisdiction = fin.declare_tax_jurisdiction(
        log, "UK", AS_OF - 100 * 86_400, AS_OF + 265 * 86_400)
    fin.tax_resident_in(log, first.id, jurisdiction.id)
    fin.tax_resident_in(log, second.id, jurisdiction.id)

    core = EntityProjection(log)
    finance = FinanceEntityProjection(log)
    evidence = PensionEvidenceProjection(log)
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance, core))
    registry.register(FinancePensionMetricProvider(finance, core, evidence))
    scope = Subject("party", household.id)

    def metric(metric_id):
        return registry.dispatch(MetricRequest(
            metric_id,
            scope,
            AS_OF,
            assumption_set_id=assumptions.id,
        ))

    return {
        "log": log,
        "household": household,
        "members": (first, second),
        "accounts": (first_pension, second_pension),
        "assumptions": assumptions,
        "metric": metric,
    }


def test_p1_p2_p7_keep_pots_rates_and_payments_disjoint(tmp_path):
    fixture = _fixture(tmp_path)
    metric = fixture["metric"]

    wealth = metric("finance.pension_wealth")
    annual = metric("finance.pension_contributions_annual")
    tax_year = metric("finance.pension_contributions_tax_year")

    assert wealth.value == 62_000.0
    assert wealth.assumption_references == ()
    assert annual.value == 10_500.0
    assert tax_year.value == pytest.approx(875.0)
    assert tax_year.value != annual.value
    assert annual.evidence_references
    assert tax_year.evidence_references
    assert set(annual.evidence_references).isdisjoint(
        tax_year.evidence_references)


def test_pension_account_valuation_is_the_same_net_worth_basis(tmp_path):
    fixture = _fixture(tmp_path)
    pension = fixture["accounts"][0]
    member = fixture["members"][0]
    fin.declare_valuation(fixture["log"], pension.id, 150_000.0, "GBP", AS_OF - 1)
    scope = Subject("party", member.id)

    wealth = _pension_wealth(
        fixture["log"], scope, fixture["assumptions"].id)
    net_worth = _net_worth(fixture["log"], scope)

    assert wealth.value == net_worth.value == 150_000.0


def test_later_pension_valuation_replaces_ledger_value_for_net_worth(tmp_path):
    fixture = _fixture(tmp_path)
    pension = fixture["accounts"][0]
    member = fixture["members"][0]
    fin.declare_transaction(
        fixture["log"], pension.id, 10_000.0, "GBP", "pension_contribution", AS_OF - 5)
    fin.declare_valuation(fixture["log"], pension.id, 150_000.0, "GBP", AS_OF - 1)
    scope = Subject("party", member.id)

    assert _pension_wealth(
        fixture["log"], scope, fixture["assumptions"].id).value == 150_000.0
    assert _net_worth(fixture["log"], scope).value == 150_000.0


def test_pension_and_net_worth_share_valuation_as_of_and_ownership_rules(tmp_path):
    fixture = _fixture(tmp_path)
    pension = fixture["accounts"][0]
    member = fixture["members"][0]
    fin.declare_valuation(fixture["log"], pension.id, 150_000.0, "GBP", AS_OF - 1)

    for scope, expected in ((Subject("party", member.id), 40_000.0),
                            (Subject("party", fixture["household"].id), 62_000.0)):
        as_of = AS_OF - 10
        assert _pension_wealth(
            fixture["log"], scope, fixture["assumptions"].id, as_of).value == expected
        assert _net_worth(fixture["log"], scope, as_of).value == expected

    assert _pension_wealth(
        fixture["log"], Subject("party", member.id), fixture["assumptions"].id).value == 150_000.0
    assert _net_worth(fixture["log"], Subject("party", member.id)).value == 150_000.0


def test_pension_account_valuation_uses_existing_net_worth_fx_conversion(tmp_path):
    fixture = _fixture(tmp_path)
    pension = fixture["accounts"][0]
    member = fixture["members"][0]
    fin.declare_valuation(fixture["log"], pension.id, 100_000.0, "EUR", AS_OF - 1)
    fin.declare_exchange_rate(fixture["log"], "EUR/GBP", .9, AS_OF - 1)
    scope = Subject("party", member.id)

    assert _pension_wealth(
        fixture["log"], scope, fixture["assumptions"].id).value == 90_000.0
    assert _net_worth(fixture["log"], scope).value == 90_000.0


def test_w_star_is_inspectable_and_zero_when_secured_income_covers_need(
        tmp_path):
    fixture = _fixture(tmp_path)
    metric = fixture["metric"]

    assert metric("finance.state_pension_income_annual").value == 10_600.0
    assert metric("finance.retirement_income_required").value == 40_000.0
    required = metric("finance.retirement_wealth_required")
    assert required.value == 735_000.0
    assert required.assumption_references == tuple(
        fixture["assumptions"].provenance)

    _record(
        fixture["log"],
        fixture["members"][0].id,
        "state_pension_annual",
        40_000.0,
        at=AS_OF + 1,
    )
    # A fresh provider at the later assessment sees the superseding evidence.
    core = EntityProjection(fixture["log"])
    finance = FinanceEntityProjection(fixture["log"])
    provider = FinancePensionMetricProvider(
        finance, core, PensionEvidenceProjection(fixture["log"]))
    zero = provider.calculate(MetricRequest(
        "finance.retirement_wealth_required",
        Subject("party", fixture["household"].id),
        AS_OF + 1,
        assumption_set_id=fixture["assumptions"].id,
    ))
    assert zero.value == 0.0


def test_db_dc_conflict_excludes_the_account_from_both_metrics(tmp_path):
    fixture = _fixture(tmp_path)
    account = fixture["accounts"][0]
    _record(
        fixture["log"], account.id,
        "db_annual_income_accrued", 5_000.0)
    provider = FinancePensionMetricProvider(
        FinanceEntityProjection(fixture["log"]),
        EntityProjection(fixture["log"]),
        PensionEvidenceProjection(fixture["log"]),
    )
    scope = Subject("party", fixture["household"].id)
    request = lambda metric_id: MetricRequest(
        metric_id, scope, AS_OF,
        assumption_set_id=fixture["assumptions"].id)

    wealth = provider.calculate(request("finance.pension_wealth"))
    db = provider.calculate(
        request("finance.defined_benefit_income_annual"))

    assert wealth.value == 22_000.0
    assert "both a pot valuation and DB entitlement" in " ".join(
        wealth.limitations)
    assert db.status == "unavailable"


def test_pension_wealth_and_accessible_assets_are_structurally_disjoint(
        tmp_path):
    fixture = _fixture(tmp_path)
    accessible = fin.declare_account(
        fixture["log"], "savings", "GBP",
        liquidity_classification="liquid")
    fin.link_ownership(
        fixture["log"], "account", accessible.id, "owner",
        fixture["members"][0].id)
    fin.declare_transaction(
        fixture["log"], accessible.id, 5_000.0, "GBP", "other", AS_OF)

    core = EntityProjection(fixture["log"])
    finance = FinanceEntityProjection(fixture["log"])
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance, core))
    registry.register(FinancePensionMetricProvider(
        finance, core, PensionEvidenceProjection(fixture["log"])))
    scope = Subject("party", fixture["household"].id)
    accessible_result = registry.dispatch(MetricRequest(
        "finance.accessible_assets", scope, AS_OF))
    pension_result = registry.dispatch(MetricRequest(
        "finance.pension_wealth", scope, AS_OF,
        assumption_set_id=fixture["assumptions"].id))

    assert accessible_result.value == 5_000.0
    assert pension_result.value == 62_000.0
    assert set(accessible_result.input_references).isdisjoint(
        pension_result.input_references)


def test_mixed_tax_year_boundaries_are_unsupported_not_silently_selected(
        tmp_path):
    fixture = _fixture(tmp_path)
    other = fin.declare_tax_jurisdiction(
        fixture["log"], "OTHER",
        AS_OF - 200 * 86_400,
        AS_OF + 165 * 86_400,
    )
    fin.tax_resident_in(
        fixture["log"], fixture["members"][1].id, other.id)
    provider = FinancePensionMetricProvider(
        FinanceEntityProjection(fixture["log"]),
        EntityProjection(fixture["log"]),
        PensionEvidenceProjection(fixture["log"]),
    )

    result = provider.calculate(MetricRequest(
        "finance.pension_contributions_tax_year",
        Subject("party", fixture["household"].id),
        AS_OF,
        assumption_set_id=fixture["assumptions"].id,
    ))

    assert result.status == "unsupported"
    assert "conflicting tax-year boundaries" in result.limitations[0]
