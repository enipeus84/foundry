"""
The synthetic Parker-Brads household — a fixture, not a domain module.

Exercises the pipeline this package exists to validate: Core's Party/
Employer machinery, Finance's own entities and ownership relations
(001 §8, §9), and all five registered metrics (metrics.py) with enough
live state that each returns `status: available`, not merely
`unsupported`/`unavailable`. Used by the finance test suite and by
`examples/finance_demo.py`.

Household: Chris and Fiona Parker-Brads (co-owners of a joint current
account and the family home, joint obligors on its mortgage), and their
children Hamish and Harriet (household members who hold no resources of
their own — an ordinary case the aggregation rule must handle without
special-casing). Chris holds a concentrated position in his own
employer's stock in his ISA — 001 §21's worked example, stopping short
of the disposal Decision that example continues with, since Decisions
are out of scope for this validation fixture.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from foundry.core.entities import declare_employer, declare_party, employ, join_household, update_party
from foundry.eventlog import EventLog

from . import entities as fin

MONTH = 30 * 24 * 3600.0


@dataclass
class ParkerBradsHousehold:
    household_id: str
    chris_id: str
    fiona_id: str
    hamish_id: str
    harriet_id: str
    anchor_systems_id: str   # Chris's employer
    riverside_trust_id: str  # Fiona's employer
    joint_checking_id: str
    chris_savings_id: str
    chris_brokerage_id: str
    chris_pension_id: str
    family_home_id: str      # Asset
    holiday_let_id: str      # Asset, EUR-denominated
    mortgage_id: str         # Obligation
    as_of: float


def build_parker_brads_household(log: EventLog, as_of: float | None = None) -> ParkerBradsHousehold:
    as_of = time.time() if as_of is None else as_of

    household = declare_party(log, "household")
    update_party(log, household.id, {"reporting_currency": "GBP"}, reason="V1 default (001 §9)")
    chris = declare_party(log, "person")
    fiona = declare_party(log, "person")
    hamish = declare_party(log, "person")
    harriet = declare_party(log, "person")
    for member in (chris, fiona, hamish, harriet):
        join_household(log, member.id, household.id)

    anchor = declare_employer(log, "Anchor Systems", industry="software")
    riverside = declare_employer(log, "Riverside Trust", industry="education")
    employ(log, chris.id, anchor.id)
    employ(log, fiona.id, riverside.id)

    joint_checking = fin.declare_account(log, "checking", "GBP", name="Joint current account",
                                          liquidity_classification="liquid")
    fin.link_ownership(log, "account", joint_checking.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(log, "account", joint_checking.id, "co_owner", fiona.id, share=50.0)

    chris_savings = fin.declare_account(log, "savings", "GBP", name="Chris's savings",
                                         liquidity_classification="liquid")
    fin.link_ownership(log, "account", chris_savings.id, "owner", chris.id)

    chris_brokerage = fin.declare_account(log, "brokerage", "GBP", name="Chris's ISA",
                                           tax_wrapper="isa", liquidity_classification="near_liquid")
    fin.link_ownership(log, "account", chris_brokerage.id, "owner", chris.id)

    chris_pension = fin.declare_account(log, "pension", "GBP", name="Chris's workplace pension",
                                         tax_wrapper="pension_wrapper", liquidity_classification="illiquid_long")
    fin.link_ownership(log, "account", chris_pension.id, "owner", chris.id)

    family_home = fin.declare_asset(log, "property", "GBP", name="Family home",
                                     liquidity_classification="illiquid_long")
    fin.link_ownership(log, "asset", family_home.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(log, "asset", family_home.id, "co_owner", fiona.id, share=50.0)
    fin.declare_valuation(log, family_home.id, 480_000.0, "GBP", as_of - 3 * MONTH)

    # Foreign-currency holding, exercising cross-currency aggregation
    # (001 §22): its Valuation is in EUR; net_worth converts it to the
    # household's GBP reporting currency via the Exchange Rate below,
    # citing that event as an input reference.
    holiday_let = fin.declare_asset(log, "property", "EUR", name="Brittany holiday let",
                                     liquidity_classification="illiquid_long")
    fin.link_ownership(log, "asset", holiday_let.id, "co_owner", chris.id, share=50.0)
    fin.link_ownership(log, "asset", holiday_let.id, "co_owner", fiona.id, share=50.0)
    fin.declare_valuation(log, holiday_let.id, 180_000.0, "EUR", as_of - 6 * MONTH)
    fin.declare_exchange_rate(log, "EUR/GBP", 0.86, as_of - 6 * MONTH)

    # Recorded once, per 001 §8's note on `secures`/`collateralises`
    # ("the inverse phrasing of secures; recorded once, never in both
    # directions for the same pair") — `secures` only, matching 001
    # §8's own worked example.
    mortgage = fin.declare_obligation(log, "mortgage", "GBP", amount=210_000.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", chris.id, share=50.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", fiona.id, share=50.0)
    fin.link_ownership(log, "obligation", mortgage.id, "secures", family_home.id)

    # Chris's ISA: a diversified fund alongside a concentrated stake in
    # his own employer's stock (001 §21's worked example — the position
    # this fixture stops short of having him sell).
    fin.declare_position(log, chris_brokerage.id, "Global Tracker Fund", quantity=400, unit_price=62.5,
                          currency="GBP", cost_basis=20_000.0, valuation_date=as_of,
                          market_value=25_000.0, asset_category="private_equity")
    fin.declare_position(log, chris_brokerage.id, "Anchor Systems plc", quantity=2000, unit_price=6.0,
                          currency="GBP", cost_basis=8_000.0, valuation_date=as_of,
                          market_value=12_000.0, asset_category="private_equity", issuer=anchor.id)

    # Six months of income and essential/committed spend — live data
    # for finance.cash_flow and finance.liquidity_runway alike.
    for m in range(6, 0, -1):
        month_ts = as_of - m * MONTH
        fin.declare_transaction(log, joint_checking.id, 4200.0, "GBP", "income", month_ts,
                                 description="Chris salary")
        fin.declare_transaction(log, joint_checking.id, 2100.0, "GBP", "income", month_ts,
                                 description="Fiona salary")
        fin.declare_transaction(log, joint_checking.id, -1450.0, "GBP", "housing", month_ts,
                                 description="Mortgage payment")
        fin.declare_transaction(log, joint_checking.id, -180.0, "GBP", "transport", month_ts)
        fin.declare_transaction(log, joint_checking.id, -520.0, "GBP", "groceries", month_ts)
        fin.declare_transaction(log, joint_checking.id, -600.0, "GBP", "childcare", month_ts)
        fin.declare_transaction(log, joint_checking.id, -90.0, "GBP", "healthcare", month_ts)
        fin.declare_transaction(log, joint_checking.id, -300.0, "GBP", "discretionary", month_ts)
        fin.declare_transaction(log, joint_checking.id, -500.0, "GBP", "savings_transfer", month_ts,
                                 description="Transfer to Chris's savings")
        fin.declare_transaction(log, chris_savings.id, 500.0, "GBP", "savings_transfer", month_ts)

    return ParkerBradsHousehold(
        household_id=household.id, chris_id=chris.id, fiona_id=fiona.id,
        hamish_id=hamish.id, harriet_id=harriet.id,
        anchor_systems_id=anchor.id, riverside_trust_id=riverside.id,
        joint_checking_id=joint_checking.id, chris_savings_id=chris_savings.id,
        chris_brokerage_id=chris_brokerage.id, chris_pension_id=chris_pension.id,
        family_home_id=family_home.id, holiday_let_id=holiday_let.id, mortgage_id=mortgage.id,
        as_of=as_of,
    )
