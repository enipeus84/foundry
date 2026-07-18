"""Unit tests: the first five registered Finance metrics (001 §13),
each a deterministic Fact over FinanceEntityProjection + Core's own
EntityProjection, dispatched only through the Metric Registry (000
§13.5) — never called directly by a test that stands in for Core."""

import time

import pytest

from foundry.core.entities import EntityProjection, declare_employer, declare_party, employ, \
    join_household, update_party
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.scope import Subject
from foundry.finance import entities as fin
from foundry.finance.metrics import FinanceMetricProvider

NOW = time.time()


def _household_of_two(log):
    household = declare_party(log, "household")
    a = declare_party(log, "person")
    b = declare_party(log, "person")
    join_household(log, a.id, household.id)
    join_household(log, b.id, household.id)
    return household, a, b


def _provider(log):
    return FinanceMetricProvider(fin.FinanceEntityProjection(log), EntityProjection(log))


def _registry(log):
    registry = MetricRegistry()
    registry.register(_provider(log))
    return registry


# --------------------------------------------------------------- net worth

def test_net_worth_household_union_and_individual_shares_reconcile(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(kernel.log, "account", account.id, "co_owner", fiona.id, share=50.0)
    fin.declare_transaction(kernel.log, account.id, 1000.0, "GBP", "income", NOW)

    registry = _registry(kernel.log)
    household_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    chris_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    fiona_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", fiona.id), as_of=NOW))

    assert household_result.value == 1000.0
    assert chris_result.value == fiona_result.value == 500.0
    assert chris_result.value + fiona_result.value == household_result.value  # 001 §9, criterion 9


def test_net_worth_joint_asset_counted_once_not_per_co_owner(kernel):
    """A jointly-owned resource must not be double-counted in the
    household total (001 §24, criterion 11)."""
    household, chris, fiona = _household_of_two(kernel.log)
    home = fin.declare_asset(kernel.log, "property", "GBP")
    fin.link_ownership(kernel.log, "asset", home.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(kernel.log, "asset", home.id, "co_owner", fiona.id, share=50.0)
    fin.declare_valuation(kernel.log, home.id, 400_000.0, "GBP", NOW)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == 400_000.0  # not 800,000


def test_net_worth_subtracts_owed_obligations(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    mortgage = fin.declare_obligation(kernel.log, "mortgage", "GBP", amount=100_000.0)
    fin.link_ownership(kernel.log, "obligation", mortgage.id, "owes", chris.id, share=50.0)
    fin.link_ownership(kernel.log, "obligation", mortgage.id, "owes", fiona.id, share=50.0)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == -100_000.0
    chris_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    assert chris_result.value == -50_000.0


def test_net_worth_ignores_ownership_link_targeting_the_household(kernel):
    """001 §9: the group Party must never be an ownership target. If a
    caller improperly writes one anyway, aggregation is defensive: the
    household total is a union over *members'* holdings, so a link
    targeting the household id itself never brings value into any
    scope — it neither inflates the household total nor crashes."""
    household, chris, fiona = _household_of_two(kernel.log)
    proper = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", proper.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, proper.id, 100.0, "GBP", "income", NOW)

    improper = fin.declare_account(kernel.log, "savings", "GBP")
    fin.link_ownership(kernel.log, "account", improper.id, "owner", household.id)  # forbidden by 001 §9
    fin.declare_transaction(kernel.log, improper.id, 9999.0, "GBP", "income", NOW)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == 100.0  # the improperly-linked account contributes nothing


def test_custodian_and_beneficiary_do_not_count_beneficial_owner_does(kernel):
    """001 §8's relation table: custodian manages *on behalf of
    another*; beneficiary is entitled to a *future* benefit; a
    beneficial owner has present economic benefit. Only the last
    confers counted value (vocab.VALUE_OWNERSHIP_RELATIONS)."""
    custodian = declare_party(kernel.log, "person")
    child = declare_party(kernel.log, "person")
    account = fin.declare_account(kernel.log, "savings", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", child.id)
    fin.link_ownership(kernel.log, "account", account.id, "custodian", custodian.id)
    fin.declare_transaction(kernel.log, account.id, 1000.0, "GBP", "income", NOW)

    trust_asset = fin.declare_asset(kernel.log, "other", "GBP")
    fin.link_ownership(kernel.log, "asset", trust_asset.id, "beneficial_owner", custodian.id)
    fin.declare_valuation(kernel.log, trust_asset.id, 500.0, "GBP", NOW)

    registry = _registry(kernel.log)
    child_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", child.id), as_of=NOW))
    custodian_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", custodian.id), as_of=NOW))
    assert child_result.value == 1000.0    # the custodial account is the child's
    assert custodian_result.value == 500.0  # beneficial ownership counts; custodianship doesn't


def test_guarantees_is_not_a_counted_liability(kernel):
    """A guarantor is liable only on default by the primary obligor
    (001 §8) — a contingent exposure, not a present one, so it never
    reduces the guarantor's net worth; only `owes` does."""
    obligor = declare_party(kernel.log, "person")
    guarantor = declare_party(kernel.log, "person")
    loan = fin.declare_obligation(kernel.log, "personal_loan", "GBP", amount=10_000.0)
    fin.link_ownership(kernel.log, "obligation", loan.id, "owes", obligor.id)
    fin.link_ownership(kernel.log, "obligation", loan.id, "guarantees", guarantor.id)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", guarantor.id)
    fin.declare_transaction(kernel.log, account.id, 500.0, "GBP", "income", NOW)

    registry = _registry(kernel.log)
    obligor_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", obligor.id), as_of=NOW))
    guarantor_result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", guarantor.id), as_of=NOW))
    assert obligor_result.value == -10_000.0
    assert guarantor_result.value == 500.0  # the guarantee never subtracts


# ------------------------------------------------------- historical (as_of)

def test_net_worth_as_of_excludes_later_transactions(kernel):
    """A transaction dated after `as_of` must not leak into a
    historical result (001 §24, criterion 8's spirit applied to
    request time; 000 §13.2: as_of is 'the point in time the value
    should reflect')."""
    chris = declare_party(kernel.log, "person")
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 1000.0, "GBP", "income", NOW - 100)
    fin.declare_transaction(kernel.log, account.id, 5000.0, "GBP", "income", NOW + 100)

    registry = _registry(kernel.log)
    historical = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    later = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW + 200))
    assert historical.value == 1000.0
    assert later.value == 6000.0


def test_net_worth_as_of_uses_the_valuation_current_at_that_time(kernel):
    chris = declare_party(kernel.log, "person")
    home = fin.declare_asset(kernel.log, "property", "GBP")
    fin.link_ownership(kernel.log, "asset", home.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, home.id, 400_000.0, "GBP", NOW - 1000)
    fin.declare_valuation(kernel.log, home.id, 500_000.0, "GBP", NOW + 1000)

    registry = _registry(kernel.log)
    then = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    now = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW + 2000))
    assert then.value == 400_000.0   # the later revaluation hasn't happened yet
    assert now.value == 500_000.0


def test_asset_valued_only_after_as_of_is_excluded_and_named(kernel):
    chris = declare_party(kernel.log, "person")
    home = fin.declare_asset(kernel.log, "property", "GBP")
    fin.link_ownership(kernel.log, "asset", home.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, home.id, 400_000.0, "GBP", NOW + 1000)  # future-dated only
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 100.0, "GBP", "income", NOW - 10)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    assert result.value == 100.0
    assert any("valued only after as_of" in l for l in result.limitations)


def test_exchange_rate_dated_after_as_of_never_applies_retroactively(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    villa = fin.declare_asset(kernel.log, "property", "EUR")
    fin.link_ownership(kernel.log, "asset", villa.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, villa.id, 100_000.0, "EUR", NOW - 10)
    fin.declare_exchange_rate(kernel.log, "EUR/GBP", 0.9, NOW + 100)  # observed only later
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 500.0, "GBP", "income", NOW - 10)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == 500.0  # the EUR villa is excluded — no rate was known at as_of
    assert any("no exchange rate" in l for l in result.limitations)


# ------------------------------------------------- projection-shaped requests

def test_projection_shaped_requests_fail_closed_as_unsupported(kernel):
    """RFC-002 Part 1 implements no Financial Projection model (001
    §16). A request carrying horizon, assumption_set_id, or scenario_id
    must return unsupported — never a silently-Baseline value
    masquerading as the projection that was asked for (000 §13.4)."""
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 1000.0, "GBP", "income", NOW)
    registry = _registry(kernel.log)
    scope = Subject("party", household.id)

    for shaped in (
        MetricRequest("finance.net_worth", scope, NOW, horizon=(NOW, NOW + 1000)),
        MetricRequest("finance.net_worth", scope, NOW, assumption_set_id="assumptions-1"),
        MetricRequest("finance.net_worth", scope, NOW, scenario_id="scenario-1"),
    ):
        result = registry.dispatch(shaped)
        assert result.status == "unsupported", shaped
        assert result.value is None

    # A plain request against the same data still works:
    assert registry.dispatch(MetricRequest("finance.net_worth", scope, NOW)).value == 1000.0


def test_unreproducible_calculation_version_fails_closed(kernel):
    """000 §13.4: a provider returns unsupported for a
    requested_calculation_version it can no longer reproduce; the
    current version is honoured."""
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 1000.0, "GBP", "income", NOW)
    registry = _registry(kernel.log)
    scope = Subject("party", household.id)

    from foundry.finance.metrics import CALCULATION_VERSION
    stale = registry.dispatch(MetricRequest(
        "finance.net_worth", scope, NOW, requested_calculation_version="v0"))
    current = registry.dispatch(MetricRequest(
        "finance.net_worth", scope, NOW, requested_calculation_version=CALCULATION_VERSION))
    assert stale.status == "unsupported" and stale.value is None
    assert current.status == "available" and current.value == 1000.0


def test_net_worth_unsupported_for_non_party_scope(kernel):
    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("employer", "acme"), as_of=NOW))
    assert result.status == "unsupported"
    assert result.value is None


def test_net_worth_unavailable_not_zero_when_nothing_observed(kernel):
    """No data yet is `unavailable`, distinct from `unsupported` (000
    §13.3) — never a fabricated zero."""
    chris = declare_party(kernel.log, "person")
    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", chris.id), as_of=NOW))
    assert result.status == "unavailable"
    assert result.value is None


def test_net_worth_cross_currency_conversion_cites_exchange_rate(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    update_party(kernel.log, household.id, {"reporting_currency": "GBP"}, reason="set")
    villa = fin.declare_asset(kernel.log, "property", "EUR")
    fin.link_ownership(kernel.log, "asset", villa.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, villa.id, 100_000.0, "EUR", NOW - 10)
    fin.declare_exchange_rate(kernel.log, "EUR/GBP", 0.9, NOW - 5)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == pytest.approx(90_000.0)
    # 001 §22: any cross-currency calculation must cite the specific
    # Exchange Rate event(s) used.
    assert any(kernel.log.get(rid)["kind"] == "finance.exchange_rate.declared"
               for rid in result.input_references)


def test_net_worth_missing_exchange_rate_excludes_item_and_flags_limitation(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    villa = fin.declare_asset(kernel.log, "property", "EUR")
    fin.link_ownership(kernel.log, "asset", villa.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, villa.id, 100_000.0, "EUR", NOW)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 500.0, "GBP", "income", NOW)
    # No exchange rate declared at all.

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == 500.0  # the EUR villa is excluded, not guessed at
    assert result.status == "available"
    assert len(result.limitations) == 1


# ---------------------------------------------------------- liquidity runway

def test_liquidity_runway_months(kernel):
    """Liquid holdings live in one account; essential/committed spend
    lives in a separate, non-liquidity-classified account — isolating
    the numerator from the denominator so the expected ratio is exact,
    rather than depending on one account's own net ledger balance after
    its own committed spend (which `_account_value`'s ledger-sum rule
    would otherwise fold into "liquid holdings" too)."""
    household, chris, fiona = _household_of_two(kernel.log)
    savings = fin.declare_account(kernel.log, "savings", "GBP", liquidity_classification="liquid")
    fin.link_ownership(kernel.log, "account", savings.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, savings.id, 6000.0, "GBP", "income", NOW - 60)

    bills_account = fin.declare_account(kernel.log, "checking", "GBP")  # no liquidity_classification
    fin.link_ownership(kernel.log, "account", bills_account.id, "owner", chris.id)
    for m in range(1, 4):
        fin.declare_transaction(kernel.log, bills_account.id, -1000.0, "GBP", "housing", NOW - m * 30 * 24 * 3600)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.liquidity_runway", scope=Subject("party", household.id), as_of=NOW))
    assert result.status == "available"
    assert result.unit_or_currency == "months"
    assert result.value == pytest.approx(6000.0 / 1000.0)  # liquid holdings / avg monthly essential spend


def test_liquidity_runway_refund_nets_against_burn_never_inflates_it(kernel):
    """A refund in an essential category reduces the burn it refunds.
    When refunds fully cancel spend (zero or negative net burn), the
    metric is unavailable — a runway over a non-positive denominator
    would be meaningless, and fabricating one is forbidden."""
    household, chris, fiona = _household_of_two(kernel.log)
    savings = fin.declare_account(kernel.log, "savings", "GBP", liquidity_classification="liquid")
    fin.link_ownership(kernel.log, "account", savings.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, savings.id, 6000.0, "GBP", "income", NOW - 60)

    bills = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", bills.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, bills.id, -300.0, "GBP", "groceries", NOW - 50)
    fin.declare_transaction(kernel.log, bills.id, 100.0, "GBP", "groceries", NOW - 40)  # partial refund

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.liquidity_runway", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == pytest.approx(6000.0 / 200.0)  # net burn 200, not |300|+|100|=400

    # Refund the rest: net burn reaches zero -> unavailable, not infinity.
    fin.declare_transaction(kernel.log, bills.id, 200.0, "GBP", "groceries", NOW - 30)
    zero_burn = _registry(kernel.log).dispatch(MetricRequest(
        metric_id="finance.liquidity_runway", scope=Subject("party", household.id), as_of=NOW))
    assert zero_burn.status == "unavailable"
    assert zero_burn.value is None


def test_liquidity_runway_unavailable_without_essential_spend_history(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "savings", "GBP", liquidity_classification="liquid")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 6000.0, "GBP", "income", NOW)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.liquidity_runway", scope=Subject("party", household.id), as_of=NOW))
    assert result.status == "unavailable"


def test_illiquid_holdings_are_excluded_from_liquidity_runway(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    home = fin.declare_asset(kernel.log, "property", "GBP", liquidity_classification="illiquid_long")
    fin.link_ownership(kernel.log, "asset", home.id, "owner", chris.id)
    fin.declare_valuation(kernel.log, home.id, 400_000.0, "GBP", NOW)

    checking = fin.declare_account(kernel.log, "checking", "GBP", liquidity_classification="liquid")
    fin.link_ownership(kernel.log, "account", checking.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, checking.id, 2000.0, "GBP", "income", NOW - 40)

    bills_account = fin.declare_account(kernel.log, "savings", "GBP")  # no liquidity_classification
    fin.link_ownership(kernel.log, "account", bills_account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, bills_account.id, -200.0, "GBP", "groceries", NOW - 10)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.liquidity_runway", scope=Subject("party", household.id), as_of=NOW))
    # £2,000 liquid / £200 monthly essential spend = 10 months — the
    # £400k illiquid home never enters the numerator at all.
    assert result.value == pytest.approx(2000.0 / 200.0)


# --------------------------------------------------------------------- cash flow

def test_cash_flow_net_across_all_categories(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 2000.0, "GBP", "income", NOW)
    fin.declare_transaction(kernel.log, account.id, -300.0, "GBP", "groceries", NOW)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", household.id), as_of=NOW))
    assert result.value == 1700.0


def test_cash_flow_single_category_via_parameters(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_transaction(kernel.log, account.id, 2000.0, "GBP", "income", NOW)
    fin.declare_transaction(kernel.log, account.id, -300.0, "GBP", "groceries", NOW)

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", household.id), as_of=NOW,
        parameters={"transaction_category": "groceries"}))
    assert result.value == -300.0


def test_cash_flow_rejects_invalid_category_parameter(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", household.id), as_of=NOW,
        parameters={"transaction_category": "not_a_real_category"}))
    assert result.status == "unsupported"


def test_cash_flow_individual_attribution_reconciles_for_a_joint_account(kernel):
    """001 §9's reconciliation criterion applied to flows: a joint
    account's transactions are attributed to each co-owner by share,
    so per-member cash flows sum to the household's total — never
    double it."""
    household, chris, fiona = _household_of_two(kernel.log)
    joint = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", joint.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(kernel.log, "account", joint.id, "co_owner", fiona.id, share=50.0)
    fin.declare_transaction(kernel.log, joint.id, 2000.0, "GBP", "income", NOW)
    fin.declare_transaction(kernel.log, joint.id, -400.0, "GBP", "groceries", NOW)

    registry = _registry(kernel.log)
    household_result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", household.id), as_of=NOW))
    chris_result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", chris.id), as_of=NOW))
    fiona_result = registry.dispatch(MetricRequest(
        metric_id="finance.cash_flow", scope=Subject("party", fiona.id), as_of=NOW))

    assert household_result.value == 1600.0
    assert chris_result.value == fiona_result.value == 800.0
    assert chris_result.value + fiona_result.value == household_result.value


# --------------------------------------------------------------- asset allocation

def test_asset_allocation_requires_category_parameter(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.asset_allocation", scope=Subject("party", household.id), as_of=NOW))
    assert result.status == "unsupported"


def test_asset_allocation_ratio_and_categories_sum_to_one(kernel):
    household, chris, fiona = _household_of_two(kernel.log)
    account = fin.declare_account(kernel.log, "brokerage", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_position(kernel.log, account.id, "Fund A", quantity=1, unit_price=750.0, currency="GBP",
                          cost_basis=600.0, valuation_date=NOW, market_value=750.0, asset_category="private_equity")
    fin.declare_position(kernel.log, account.id, "Cash equivalents", quantity=1, unit_price=250.0, currency="GBP",
                          cost_basis=250.0, valuation_date=NOW, market_value=250.0, asset_category="cash_equivalent")

    registry = _registry(kernel.log)
    scope = Subject("party", household.id)
    equity = registry.dispatch(MetricRequest(
        metric_id="finance.asset_allocation", scope=scope, as_of=NOW,
        parameters={"asset_category": "private_equity"}))
    cash = registry.dispatch(MetricRequest(
        metric_id="finance.asset_allocation", scope=scope, as_of=NOW,
        parameters={"asset_category": "cash_equivalent"}))
    assert equity.value == pytest.approx(0.75)
    assert cash.value == pytest.approx(0.25)
    assert equity.value + cash.value == pytest.approx(1.0)  # complete inputs reconcile to 100%


def test_asset_allocation_joint_account_positions_counted_once(kernel):
    """Union-by-entity-id holds for allocation too: a jointly-owned
    brokerage's positions enter the denominator once, not once per
    co-owner."""
    household, chris, fiona = _household_of_two(kernel.log)
    joint = fin.declare_account(kernel.log, "brokerage", "GBP")
    fin.link_ownership(kernel.log, "account", joint.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(kernel.log, "account", joint.id, "co_owner", fiona.id, share=50.0)
    fin.declare_position(kernel.log, joint.id, "Fund A", quantity=1, unit_price=600.0, currency="GBP",
                          cost_basis=500.0, valuation_date=NOW, market_value=600.0, asset_category="private_equity")
    fin.declare_position(kernel.log, joint.id, "Cash", quantity=1, unit_price=400.0, currency="GBP",
                          cost_basis=400.0, valuation_date=NOW, market_value=400.0, asset_category="cash_equivalent")

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.asset_allocation", scope=Subject("party", household.id), as_of=NOW,
        parameters={"asset_category": "private_equity"}))
    assert result.value == pytest.approx(0.6)  # 600/1000, not 1200/2000-with-drift or double-counting


# ---------------------------------------------------------- employer concentration

def test_employer_concentration_uses_core_employer_no_string_matching(kernel):
    """001 §24, criterion 18: derivable from Position + the core
    Employer entity + core employed_by links alone."""
    chris = declare_party(kernel.log, "person")
    acme = declare_employer(kernel.log, "Acme Corp")
    employ(kernel.log, chris.id, acme.id)
    account = fin.declare_account(kernel.log, "brokerage", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", chris.id)
    fin.declare_position(kernel.log, account.id, "Acme plc", quantity=1, unit_price=2400.0, currency="GBP",
                          cost_basis=2000.0, valuation_date=NOW, market_value=2400.0,
                          asset_category="private_equity", issuer=acme.id)
    fin.declare_position(kernel.log, account.id, "Fund B", quantity=1, unit_price=7600.0, currency="GBP",
                          cost_basis=7000.0, valuation_date=NOW, market_value=7600.0, asset_category="private_equity")

    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.employer_concentration", scope=Subject("party", chris.id), as_of=NOW))
    assert result.value == pytest.approx(0.24)


def test_employer_concentration_unavailable_without_declared_employer(kernel):
    chris = declare_party(kernel.log, "person")
    registry = _registry(kernel.log)
    result = registry.dispatch(MetricRequest(
        metric_id="finance.employer_concentration", scope=Subject("party", chris.id), as_of=NOW))
    assert result.status == "unavailable"


# ------------------------------------------------------------------ registry

def test_all_five_metrics_registered(kernel):
    provider = _provider(kernel.log)
    assert provider.owned_metric_ids() == {
        "finance.net_worth", "finance.liquidity_runway", "finance.cash_flow",
        "finance.asset_allocation", "finance.employer_concentration",
    }


def test_unknown_finance_metric_id_falls_through_to_unsupported(kernel):
    provider = _provider(kernel.log)
    result = provider.calculate(MetricRequest(
        metric_id="finance.not_a_real_metric", scope=Subject("party", "p1"), as_of=NOW))
    assert result.status == "unsupported"


def test_no_model_adapter_import_in_finance_metrics_module():
    """AI must never calculate a deterministic metric (000 §13,
    design principle 5) — enforced by absence, the same discipline
    foundry.core.metrics already establishes for itself."""
    import ast
    import inspect

    import foundry.finance.metrics as metrics_module
    tree = ast.parse(inspect.getsource(metrics_module))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | \
        {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "foundry.models" not in imported
    assert "foundry.kernel" not in imported
