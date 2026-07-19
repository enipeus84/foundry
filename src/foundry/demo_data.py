"""
Synthetic Morgan household — ~24 months of realistic event history for
evaluating Mission Control end to end (RFC-003.2), plus the demo-mode
startup hook that lets a deployed instance seed itself (RFC-003.3).

*** THIS IS SYNTHETIC DATA. Not a real household. Not an import feature.
*** Not an onboarding workflow. Purely a design dataset so Mission
*** Control can be exercised under realistic operating conditions
*** before any personal data is introduced.

Everything below is written through Core's and Finance's own public
write functions, onto a single append-only EventLog — the same
discipline `foundry.finance.fixtures.build_parker_brads_household` and
`examples/seed_mission_control.py` already use. Nothing here writes to
a projection directly, nothing bypasses the vocabularies those write
functions enforce, and nothing skips the Event Log. The dataset must
replay like a genuine household because it is built the same way one
would be: one event at a time, through the same API a real integration
would call.

This module lives in `foundry` proper (not `examples/`) so both the
CLI (`examples/seed_synthetic_household.py`, a thin wrapper) and the
web layer's optional demo-mode startup hook (`ensure_demo_data`, used
by `foundry.web`) can import it without reaching into an unpackaged,
uninstalled directory.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

from foundry.core import grammar as core_grammar
from foundry.core import vocab as core_vocab
from foundry.core.decisions import (
    concern_decision, concern_outcome, declare_decision, declare_outcome,
    declare_review, inform_decision,
)
from foundry.core.entities import (
    declare_employer, declare_mission, declare_party, employ, join_household, update_party,
)
from foundry.core.evidence import concern, derive_claim_directly, tag_claim
from foundry.eventlog import EventLog
from foundry.finance import entities as fin

logger = logging.getLogger("foundry.demo_data")

DAY = 24 * 3600.0
MONTH = 30 * DAY

# Fixed so the *content* this script generates — which months get a
# bonus, the unexpected-repair date, jitter on transaction days — is
# reproducible run to run. This is independent of event ids and the
# envelope `ts` EventLog.append stamps on every write (always real
# wall-clock time, same as every other writer in this codebase) — two
# runs never produce byte-identical logs, and nothing requires that;
# replay determinism (this dataset's actual guarantee) means two
# independent projections built from *one* log agree exactly, which
# holds regardless of when or how many times that log was written.
SEED = 20250719


@dataclass
class MorganHousehold:
    household_id: str
    alex_id: str
    sam_id: str
    emily_id: str
    oliver_id: str
    nimbus_id: str          # Alex's employer
    bellwether_id: str      # Sam's employer
    joint_checking_id: str
    joint_savings_id: str
    emergency_fund_id: str
    alex_isa_id: str
    alex_pension_id: str
    sam_pension_id: str
    credit_card_id: str
    family_home_id: str
    vehicle_id: str
    us_savings_id: str      # foreign-currency asset
    mortgage_id: str
    nimbus_position_id: str
    tracker_position_id: str
    as_of: float


def build_morgan_household(log: EventLog, as_of: float | None = None) -> MorganHousehold:
    as_of = time.time() if as_of is None else as_of
    rnd = random.Random(SEED)

    def m_ago(months: float, jitter_days: float = 2.0) -> float:
        return as_of - months * MONTH + rnd.uniform(-jitter_days, jitter_days) * DAY

    # ------------------------------------------------------------ household
    household = declare_party(log, "household")
    update_party(log, household.id, {"reporting_currency": "GBP"}, reason="V1 default (001 §9)")
    alex = declare_party(log, "person")
    sam = declare_party(log, "person")
    emily = declare_party(log, "person")
    oliver = declare_party(log, "person")
    for member in (alex, sam, emily, oliver):
        join_household(log, member.id, household.id)

    nimbus = declare_employer(log, "Nimbus Robotics", industry="robotics")
    bellwether = declare_employer(log, "Bellwether Health Partners", industry="healthcare")
    employ(log, alex.id, nimbus.id)
    employ(log, sam.id, bellwether.id)

    jurisdiction = fin.declare_tax_jurisdiction(log, "UK", tax_year_start=m_ago(15), tax_year_end=m_ago(3))
    fin.tax_resident_in(log, alex.id, jurisdiction.id)
    fin.tax_resident_in(log, sam.id, jurisdiction.id)
    fin.declare_tax_position(log, household.id, tax_year="2024/25", jurisdiction_id=jurisdiction.id,
                              estimation_basis="estimated", amount=9_800.0)

    # ------------------------------------------------------------- accounts
    joint_checking = fin.declare_account(log, "checking", "GBP", name="Morgan joint current account",
                                          liquidity_classification="liquid")
    fin.link_ownership(log, "account", joint_checking.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "account", joint_checking.id, "co_owner", sam.id, share=50.0)

    joint_savings = fin.declare_account(log, "savings", "GBP", name="Morgan joint savings",
                                         liquidity_classification="liquid")
    fin.link_ownership(log, "account", joint_savings.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "account", joint_savings.id, "co_owner", sam.id, share=50.0)

    emergency_fund = fin.declare_account(log, "savings", "GBP", name="Emergency fund",
                                          liquidity_classification="liquid")
    fin.link_ownership(log, "account", emergency_fund.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "account", emergency_fund.id, "co_owner", sam.id, share=50.0)

    alex_isa = fin.declare_account(log, "brokerage", "GBP", name="Alex's Stocks & Shares ISA",
                                    tax_wrapper="isa", liquidity_classification="near_liquid")
    fin.link_ownership(log, "account", alex_isa.id, "owner", alex.id)

    alex_pension = fin.declare_account(log, "pension", "GBP", name="Alex's workplace pension",
                                        tax_wrapper="pension_wrapper", liquidity_classification="illiquid_long")
    fin.link_ownership(log, "account", alex_pension.id, "owner", alex.id)

    sam_pension = fin.declare_account(log, "pension", "GBP", name="Sam's workplace pension",
                                       tax_wrapper="pension_wrapper", liquidity_classification="illiquid_long")
    fin.link_ownership(log, "account", sam_pension.id, "owner", sam.id)

    # Deliberately no `liquidity_classification`: a credit card balance
    # is neither spendable cash nor a near-liquid holding — it should
    # affect net worth and debt (via its ledger balance) but never the
    # liquidity-runway or cash-available numerators.
    credit_card = fin.declare_account(log, "credit_card", "GBP", name="Morgan household credit card")
    fin.link_ownership(log, "account", credit_card.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "account", credit_card.id, "co_owner", sam.id, share=50.0)

    # --------------------------------------------------------------- assets
    family_home = fin.declare_asset(log, "property", "GBP", name="Morgan family home",
                                     liquidity_classification="illiquid_long")
    fin.link_ownership(log, "asset", family_home.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "asset", family_home.id, "co_owner", sam.id, share=50.0)
    # House appreciation: three snapshots across the window.
    fin.declare_valuation(log, family_home.id, 415_000.0, "GBP", m_ago(22))
    fin.declare_valuation(log, family_home.id, 432_000.0, "GBP", m_ago(10))
    fin.declare_valuation(log, family_home.id, 448_000.0, "GBP", m_ago(1))

    vehicle = fin.declare_asset(log, "vehicle", "GBP", name="Family car (estate)",
                                 liquidity_classification="illiquid_short")
    fin.link_ownership(log, "asset", vehicle.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "asset", vehicle.id, "co_owner", sam.id, share=50.0)
    # Steady depreciation.
    fin.declare_valuation(log, vehicle.id, 24_000.0, "GBP", m_ago(20))
    fin.declare_valuation(log, vehicle.id, 19_500.0, "GBP", m_ago(10))
    fin.declare_valuation(log, vehicle.id, 16_800.0, "GBP", m_ago(2))

    # Foreign-currency asset (001 §22 cross-currency aggregation),
    # exercised with its own Exchange Rate events across the window —
    # a rate that moves and moves back, the same "decline then
    # recovery" shape as the equity holdings below, told through FX
    # instead of price.
    us_savings = fin.declare_asset(log, "cash_equivalent", "USD", name="Legacy US relocation savings",
                                    liquidity_classification="liquid")
    fin.link_ownership(log, "asset", us_savings.id, "co_owner", alex.id, share=50.0)
    fin.link_ownership(log, "asset", us_savings.id, "co_owner", sam.id, share=50.0)
    fin.declare_valuation(log, us_savings.id, 15_800.0, "USD", m_ago(2))
    fin.declare_exchange_rate(log, "USD/GBP", 0.79, m_ago(20))
    fin.declare_exchange_rate(log, "USD/GBP", 0.75, m_ago(8))
    fin.declare_exchange_rate(log, "USD/GBP", 0.80, m_ago(1))

    # ------------------------------------------------------------ mortgage
    mortgage = fin.declare_obligation(log, "mortgage", "GBP", amount=240_000.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", alex.id, share=50.0)
    fin.link_ownership(log, "obligation", mortgage.id, "owes", sam.id, share=50.0)
    fin.link_ownership(log, "obligation", mortgage.id, "secures", family_home.id)
    for amount in (235_000.0, 229_500.0, 223_800.0, 218_500.0):
        fin.update_obligation(log, mortgage.id, amount, reason="Scheduled capital repayment", actor="user")

    # ------------------------------------------------------------ positions
    # Alex's ISA: a diversified tracker fund alongside a concentrated
    # stake in Alex's own employer's stock — the same shape 001 §21's
    # worked example uses, carried all the way through a disposal
    # Decision this time (see the lifecycle below).
    tracker = fin.declare_position(log, alex_isa.id, "Global Diversified Tracker Fund", quantity=800,
                                    unit_price=43.75, currency="GBP", cost_basis=30_000.0,
                                    valuation_date=m_ago(22), market_value=35_000.0,
                                    asset_category="other")
    nimbus_pos = fin.declare_position(log, alex_isa.id, "Nimbus Robotics plc", quantity=3_000,
                                       unit_price=5.33, currency="GBP", cost_basis=12_000.0,
                                       valuation_date=m_ago(22), market_value=16_000.0,
                                       asset_category="private_equity", issuer=nimbus.id)
    # Broad market decline, ~14 months in.
    fin.update_position(log, tracker.id, "Market decline", actor="user",
                         market_value=30_800.0, unit_price=38.5, valuation_date=m_ago(14))
    fin.update_position(log, nimbus_pos.id, "Market decline", actor="user",
                         market_value=14_100.0, unit_price=4.7, valuation_date=m_ago(14))

    return MorganHousehold(
        household_id=household.id, alex_id=alex.id, sam_id=sam.id,
        emily_id=emily.id, oliver_id=oliver.id,
        nimbus_id=nimbus.id, bellwether_id=bellwether.id,
        joint_checking_id=joint_checking.id, joint_savings_id=joint_savings.id,
        emergency_fund_id=emergency_fund.id, alex_isa_id=alex_isa.id,
        alex_pension_id=alex_pension.id, sam_pension_id=sam_pension.id,
        credit_card_id=credit_card.id, family_home_id=family_home.id,
        vehicle_id=vehicle.id, us_savings_id=us_savings.id, mortgage_id=mortgage.id,
        nimbus_position_id=nimbus_pos.id, tracker_position_id=tracker.id,
        as_of=as_of,
    )


def _seed_transactions(log: EventLog, hh: MorganHousehold, as_of: float) -> None:
    """24 months of transactions, unevenly spaced: quiet months, busy
    months, a mid-window salary rise, two annual bonuses, a tax refund,
    one unexpected repair, two holidays, and a slow credit-card burn
    with quarterly repayments."""
    rnd = random.Random(SEED ^ 0xC0FFEE)

    def m_ago(months: float, jitter_days: float = 6.0) -> float:
        return as_of - months * MONTH + rnd.uniform(-jitter_days, jitter_days) * DAY

    def txn(account_id, amount, category, months_ago, description=None):
        fin.declare_transaction(log, account_id, amount, "GBP", category,
                                 m_ago(months_ago), description=description)

    checking, savings, emergency = hh.joint_checking_id, hh.joint_savings_id, hh.emergency_fund_id
    card, alex_pension, sam_pension = hh.credit_card_id, hh.alex_pension_id, hh.sam_pension_id

    bonus_months = {23, 11}          # two annual bonus cycles across the window
    repair_month = 17                # unexpected event
    holiday_months = {20, 8}         # summer + winter, roughly a year apart
    education_months = {19, 15, 9, 4}  # occasional, not monthly — a "busy" beat
    quiet_months = {21, 16, 13, 5}    # months with lighter discretionary spend
    raise_cutover = 12                # months_ago <= this uses the post-raise salary

    # A running checking-account estimate, used only to size each
    # month's sweep to savings/emergency/investment — a standing order
    # that keeps the current account near a working buffer, the way a
    # real household's does, rather than letting 24 months of
    # unswept surplus pile up in a 0%-interest checking account.
    buffer_target = 5_500.0
    running = 4_200.0

    for months_ago in range(24, 0, -1):
        alex_salary = 4_200.0 if months_ago <= raise_cutover else 3_800.0
        sam_salary = 3_100.0 if months_ago <= raise_cutover else 2_900.0
        txn(checking, alex_salary, "income", months_ago, "Alex salary — Nimbus Robotics")
        txn(checking, sam_salary, "income", months_ago, "Sam salary — Bellwether Health Partners")
        running += alex_salary + sam_salary

        if months_ago in bonus_months:
            bonus = 3_100.0 if months_ago == 23 else 3_400.0
            txn(checking, bonus, "income", months_ago, "Annual performance bonus")
            running += bonus

        if months_ago == 15:
            txn(checking, 460.0, "income", months_ago, "HMRC tax refund")
            running += 460.0

        fixed = {
            "housing_mortgage": -1_650.0, "housing_insurance": -95.0,
            "transport": -190.0 + rnd.uniform(-15, 15),
            "groceries": -750.0 + rnd.uniform(-40, 60),
            "childcare": -950.0, "healthcare": -110.0 + rnd.uniform(-20, 20),
        }
        txn(checking, fixed["housing_mortgage"], "housing", months_ago, "Mortgage payment")
        txn(checking, fixed["housing_insurance"], "housing", months_ago, "Buildings & contents insurance")
        txn(checking, fixed["transport"], "transport", months_ago, "Fuel & parking")
        txn(checking, fixed["groceries"], "groceries", months_ago)
        txn(checking, fixed["childcare"], "childcare", months_ago, "Nursery & after-school club")
        txn(checking, fixed["healthcare"], "healthcare", months_ago)
        running += sum(fixed.values())

        if months_ago in education_months:
            txn(checking, -120.0, "education", months_ago, "Extracurricular tuition")
            running -= 120.0

        discretionary = -260.0 if months_ago in quiet_months else -420.0 + rnd.uniform(-40, 60)
        txn(checking, discretionary, "discretionary", months_ago, "Everyday discretionary spend")
        running += discretionary

        if months_ago in holiday_months:
            holiday = -2_100.0 if months_ago == 20 else -1_450.0
            txn(checking, holiday, "discretionary", months_ago, "Family holiday")
            running += holiday

        if months_ago == repair_month:
            txn(checking, -1_780.0, "other", months_ago, "Unexpected boiler repair")
            running -= 1_780.0

        if months_ago == 9:
            txn(checking, -640.0, "tax_payment", months_ago, "Self-assessment payment on account")
            running -= 640.0

        # Credit card: a modest recurring charge, repaid quarterly.
        txn(card, -95.0 + rnd.uniform(-20, 40), "discretionary", months_ago, "Card spend")
        if months_ago % 3 == 0:
            txn(checking, -260.0, "other", months_ago, "Credit card repayment")
            txn(card, 260.0, "other", months_ago, "Payment received")
            running -= 260.0

        # Sweep roughly half of whatever surplus sits above the buffer
        # into savings, the emergency fund, and the ISA — the rest
        # stays in checking, the way a real balance drifts up rather
        # than snapping to a fixed number every month.
        sweep = 0.5 * max(0.0, running - buffer_target)
        running -= sweep
        emergency_amt = round(min(150.0, sweep * 0.12), 2)
        invest_amt = round(min(450.0, sweep * 0.30), 2)
        savings_amt = round(max(0.0, sweep - emergency_amt - invest_amt), 2)

        if savings_amt > 0:
            txn(checking, -savings_amt, "savings_transfer", months_ago, "Transfer to joint savings")
            txn(savings, savings_amt, "savings_transfer", months_ago)
        if emergency_amt > 0:
            txn(checking, -emergency_amt, "savings_transfer", months_ago, "Transfer to emergency fund")
            txn(emergency, emergency_amt, "savings_transfer", months_ago)
        # Investment contribution leaves the checking account; it funds
        # the ISA positions tracked separately (their market_value
        # already reflects contributed capital, so no mirrored ISA
        # ledger entry — that would double-count against the Positions).
        if invest_amt > 0:
            txn(checking, -invest_amt, "investment_contribution", months_ago, "ISA regular contribution")

        # Pension contributions post straight to the pension accounts —
        # for a pension, the ledger *is* the balance (001/RFC-002: no
        # Position layer for workplace pensions in V1).
        pension_growth = 1.0 if months_ago > raise_cutover else 1.12
        txn(alex_pension, 340.0 * pension_growth, "pension_contribution", months_ago,
            "Employee + employer contribution")
        txn(sam_pension, 260.0 * pension_growth, "pension_contribution", months_ago,
            "Employee + employer contribution")


def _seed_decision_lifecycle(log: EventLog, hh: MorganHousehold, as_of: float) -> None:
    """Mission -> Decision -> Execution -> Outcome -> Review -> Learning
    (000 §12), told through the one concrete story this dataset carries
    end to end: Alex's employer-stock concentration, flagged, decided
    on, acted on, measured, reviewed, and generalised into a standing
    practice."""

    def m_ago(months: float) -> float:
        return as_of - months * MONTH

    # Understanding: an Observation/Interpretation Claim precedes the
    # Decision it informs (000 §12's own opening stages). Its
    # provenance is Alex's own Party id — there is no `ingest` event
    # behind this observation, so it anchors directly to the subject
    # the same way a Decision Review anchors to its Decision (000 §12).
    _, observation_id = derive_claim_directly(
        log, statement="Nimbus Robotics stock is roughly 31% of Alex's ISA — "
                        "concentration risk layered on top of employment risk.",
        confidence=0.82, evidence=["Nimbus Robotics plc position valued at £14,100 "
                                    "against a £30,800 diversified tracker in the same ISA."],
        provenance=[hh.alex_id], actor="user")
    tag_claim(log, observation_id, "insight_type", "warning")
    concern(log, observation_id, hh.alex_id)
    concern(log, observation_id, hh.household_id)

    decision = declare_decision(
        log,
        statement="Partially dispose of the Nimbus Robotics position in Alex's ISA to bring "
                  "employer-stock concentration below 20%, rebalancing the proceeds into the "
                  "existing diversified tracker fund.",
        rationale="Concentration in a single employer's stock compounds job-loss risk with "
                  "equity-price risk for the same household; 001 §21's own worked example "
                  "flags this pattern.",
        expected_outcome="finance.employer_concentration falls below 20% and stays there.",
    )
    concern_decision(log, decision.id, hh.alex_id)
    concern_decision(log, decision.id, hh.household_id)
    inform_decision(log, decision.id, observation_id)

    # Execution: no dedicated entity (000 §12) — the domain mutation
    # that carries the Decision out links back `executes`. Here that's
    # the Position update selling half the Nimbus holding, plus the
    # realised gain the disposal produced.
    t_exec = m_ago(8)
    fin.update_position(log, hh.nimbus_position_id, "Partial disposal to reduce concentration",
                         actor="user", quantity=1_500, unit_price=5.0,
                         market_value=7_500.0, valuation_date=t_exec)
    core_grammar.relate(log, "finance", "position", hh.nimbus_position_id, "executes",
                         decision.id, core_vocab.STRUCTURAL_RELATIONSHIP, actor="user")
    fin.declare_capital_gain_event(log, hh.nimbus_position_id, realized_gain=1_650.0,
                                    currency="GBP", date=t_exec)
    # The tracker fund absorbs the rebalanced proceeds and, separately,
    # the broader market recovery observed over the same period.
    fin.update_position(log, hh.tracker_position_id, "Rebalance proceeds + market recovery",
                         actor="user", market_value=41_600.0, unit_price=52.0,
                         valuation_date=m_ago(5))

    outcome = declare_outcome(log, decision, observed_metric="finance.employer_concentration",
                               observed_value=0.153, observed_at=m_ago(5))
    concern_outcome(log, outcome.id, hh.alex_id)

    # The Review claim id isn't needed downstream; declare_review's
    # side effect on the log is the point.
    declare_review(
        log, decision, outcome,
        statement="The partial disposal cut Nimbus Robotics concentration from roughly 31% to "
                  "about 15% of Alex's ISA, comfortably inside the 20% target, without needing "
                  "a full exit from the position.",
        review_verdict="achieved",
        concerns=[hh.alex_id, hh.household_id],
        confidence=0.85,
        evidence_text="Employer concentration observed at ~15.3% after rebalancing, down from "
                      "~31% before the disposal.",
    )

    # Learning: a claim that generalises past this one Decision — the
    # "lessons learned become future evidence" property 000 §12
    # describes, costing no new machinery.
    _, learning_id = derive_claim_directly(
        log, statement="Review any single-employer stock position once it exceeds 25% of the "
                        "account it sits in — not only after a vesting event surfaces it.",
        confidence=0.75,
        evidence=["Nimbus Robotics concentration reached ~31% before it was first flagged."],
        provenance=[*decision.provenance, *outcome.provenance], actor="user")
    tag_claim(log, learning_id, "insight_type", "recommendation")
    concern(log, learning_id, hh.household_id)
    concern(log, learning_id, hh.alex_id)


def build(log: EventLog, as_of: float | None = None) -> MorganHousehold:
    """The whole dataset: household, 24 months of transactions, the
    Decision lifecycle, an active Mission, and the standing
    recommendation Mission Control's home page surfaces as NEXT
    DECISION. Both the CLI (`examples/seed_synthetic_household.py`) and
    demo-mode startup (`ensure_demo_data`, below) call this one
    function, so they can never drift apart."""
    as_of = time.time() if as_of is None else as_of
    hh = build_morgan_household(log, as_of=as_of)

    # Permanent in-band synthetic marker: a Claim, through the same
    # public evidence API as everything else, whose actor and statement
    # both say what this log is. Because the log is append-only and
    # Claims replay like any other event, no later inspection of this
    # file — with or without this module present — can mistake the
    # dataset for a real household. The `synthetic_demo` actor also
    # distinguishes every marker-related event from the fixture's
    # ordinary "user"-actored writes.
    _, marker_id = derive_claim_directly(
        log,
        statement="SYNTHETIC DEMO DATA: every event in this log describes the fictional "
                  "Morgan household generated by foundry.demo_data (RFC-003.2/003.3). "
                  "It contains no real persons, accounts, or finances.",
        confidence=1.0,
        evidence=["Generated by foundry.demo_data.build with fixed random seed "
                  f"{SEED}."],
        provenance=[hh.household_id],
        actor="synthetic_demo",
    )
    tag_claim(log, marker_id, "insight_type", "observation", actor="synthetic_demo")
    concern(log, marker_id, hh.household_id, actor="synthetic_demo")

    _seed_transactions(log, hh, as_of)
    _seed_decision_lifecycle(log, hh, as_of)

    declare_mission(
        log, "Coast FIRE by 2038",
        target_metric="finance.net_worth",
        target_value=420_000.0, tolerance=60_000.0,
    )

    _, claim_id = derive_claim_directly(
        log,
        statement="Set up a standing quarterly check on single-employer stock concentration "
                  "across all ISA and pension holdings, not just Alex's.",
        confidence=0.8,
        evidence=["The Nimbus Robotics disposal (2024) only happened after concentration "
                  "had already reached ~31%."],
        provenance=[hh.household_id],
        actor="user",
    )
    tag_claim(log, claim_id, "insight_type", "recommendation")
    concern(log, claim_id, hh.household_id)
    return hh


# --------------------------------------------------------------- demo mode

def _existing_log_looks_intact(path: Path) -> bool:
    """Best-effort integrity probe of a log this function has already
    decided *not to touch* — parse + hash-chain check, purely so the
    skip can be logged honestly (`skipped` vs `skipped, and by the way
    it looks corrupt`). Never raises: the answer only affects log
    severity, and a probe that could crash startup would defeat the
    point of leaving unknown data alone."""
    try:
        log = EventLog(path)
        # A non-empty file that parses to zero events (e.g. only
        # whitespace) is not an intact log — verify() alone would be
        # vacuously true for it.
        return any(True for _ in log.events()) and log.verify()
    except Exception:  # malformed JSON, unreadable file, anything
        return False


def ensure_demo_data(path: str) -> bool:
    """RFC-003.3: idempotently populate `path` with the synthetic
    Morgan household if, and only if, no log content exists there yet.

    Safety properties, each covered by tests/test_demo_data.py:

    - **Never touches existing content.** "Empty" is decided by file
      size alone — existing bytes are never parsed to make the
      decision, so a malformed, whitespace-only, or half-written file
      is preserved as evidence exactly as found (a warning names it;
      nothing "repairs" it). Only a missing file or a zero-byte file
      qualifies for seeding.
    - **Atomic.** The dataset is built in a same-directory temp file,
      its hash chain verified, then `os.replace`d onto the target in
      one step. A crash mid-seed leaves the target exactly as it was
      (missing or zero-byte) plus an inert `.tmp-<pid>` sibling that
      can never be mistaken for the log; the next start re-seeds
      cleanly. The target never holds a partially written dataset.
    - **Concurrency-safe.** A sibling `.lock` file created with
      O_CREAT|O_EXCL serialises simultaneous starts (multi-worker
      uvicorn, overlapping deploys): exactly one process seeds; the
      others skip and say so. Emptiness is re-checked under the lock.
    - **Fail closed.** An unwritable path, a path that is a directory,
      or a temp file whose chain fails verification raises out of this
      function; the caller (`foundry.web`) lets that kill startup
      rather than come up without the data it was asked for.

    Returns `True` if this call seeded the log, `False` if it skipped
    (existing content, or another process holds the seeding lock)."""
    target = Path(path)
    if target.is_dir():
        raise IsADirectoryError(
            f"FOUNDRY_DATA_PATH points at a directory, not a file: {target}")

    def has_content() -> bool:
        try:
            return target.stat().st_size > 0
        except FileNotFoundError:
            return False

    if has_content():
        if _existing_log_looks_intact(target):
            logger.info("demo data: skipped seeding %s — log already has events", path)
        else:
            logger.critical(
                "demo data: skipped seeding %s — file is non-empty but does not "
                "parse/verify as an event log; left untouched as evidence", path)
        return False

    target.parent.mkdir(parents=True, exist_ok=True)

    lock = target.with_name(target.name + ".lock")
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.warning(
            "demo data: another process holds %s — skipping seeding here. If no "
            "sibling process is seeding, the lock is stale (a crashed earlier "
            "seed); delete it to allow seeding", lock)
        return False

    try:
        os.write(lock_fd, f"{os.getpid()}\n".encode())
        os.close(lock_fd)

        if has_content():  # a sibling won the race before we locked
            logger.info("demo data: skipped seeding %s — log already has events", path)
            return False

        tmp = target.with_name(target.name + f".tmp-{os.getpid()}")
        tmp.unlink(missing_ok=True)
        tmp_log = EventLog(tmp)
        build(tmp_log)
        if not tmp_log.verify():
            raise RuntimeError(
                f"demo data: freshly built dataset at {tmp} failed hash-chain "
                f"verification — refusing to publish it")
        os.replace(tmp, target)  # atomic: the target is never part-written
        logger.info("demo data: seeded synthetic Morgan household into %s "
                    "(SYNTHETIC DATA — no real persons or finances)", path)
        return True
    finally:
        try:
            os.unlink(lock)
        except FileNotFoundError:
            pass
