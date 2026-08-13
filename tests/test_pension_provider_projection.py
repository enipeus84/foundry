"""Provider pension projections remain observations, never economic value."""

from foundry.core.entities import EntityProjection, declare_party, join_household
from foundry.core.metrics import MetricRequest
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance import entities as fin
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.metrics import FinanceMetricProvider
from foundry.finance.pension_projection import (
    PensionProviderProjectionProjection,
    record_pension_provider_projection,
)


def _record(log, account_id, observed_at=100.0, **changes):
    values = dict(provider="Aviva", observed_at=observed_at, retirement_age=67,
                  fund_low=380_000, fund_medium=604_000, fund_high=1_100_000,
                  income_low=22_500, income_medium=43_800, income_high=96_600,
                  growth_low_percent=-.8, growth_medium_percent=2.2, growth_high_percent=5.1,
                  income_basis="Provider-stated annuity/drawdown basis in supplied statement",
                  source="Aviva projection statement", lineage="household supplied statement")
    values.update(changes)
    return record_pension_provider_projection(log, account_id, **values)


def test_provider_scenarios_stay_paired_and_history_is_not_rewritten(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    first = _record(log, "pension-1")
    second = _record(log, "pension-1", 200.0, fund_medium=650_000, fund_high=1_150_000,
                     income_medium=47_000, income_high=99_000, growth_medium_percent=2.5,
                     growth_high_percent=5.4)
    view = PensionProviderProjectionProjection(log)

    assert view.for_account("pension-1", 250.0) == (first, second)
    assert view.latest("pension-1", 150.0) == first
    assert view.latest("pension-1", 250.0) == second
    assert (first.fund_low, first.fund_medium, first.fund_high) == (380_000, 604_000, 1_100_000)
    assert (second.growth_low_percent, second.growth_medium_percent, second.growth_high_percent) == (-.8, 2.5, 5.4)


def test_provider_projection_cannot_leak_into_net_worth(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    household, person = declare_party(log, "household"), declare_party(log, "person")
    join_household(log, person.id, household.id)
    pension = fin.declare_account(log, "pension", "GBP")
    fin.link_ownership(log, "account", pension.id, "owner", person.id)
    fin.declare_valuation(log, pension.id, 100_000, "GBP", 100.0)
    _record(log, pension.id)

    result = FinanceMetricProvider(FinanceEntityProjection(log), EntityProjection(log)).calculate(
        MetricRequest("finance.net_worth", Subject("party", household.id), 100.0))

    assert result.value == 100_000
