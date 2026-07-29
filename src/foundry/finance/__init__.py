"""
Foundry Finance — the first product domain built on Core
(docs/specifications/001-finance-domain-model.md).

RFC-002 established deterministic entities and registered metrics.
RFC-005 adds Assumption Set, Scenario, the first Financial Projection
engine, and Financial Independence as the first implementation of
Core's domain-neutral Mission Assessment contract.
RFC-007 adds Mortgage Freedom as the second provider and the first
proof that the RFC-006 seam accepts a new mission without shared UI
or routing branches.

Finance never redefines a Core concept and never duplicates a Core
primitive (`000` §3): Party, Employer, Mission, the Decision lifecycle,
the event grammar, the Core Evidence Index, and the Metric Registry are
all consumed from `foundry.core`, unmodified. Every mutation here is
`EventLog.append` under a `finance.` event kind; every read here is a
projection over that same log — deletable, rebuildable, and never
authoritative on its own.

    from foundry.finance import FinanceEntityProjection
    from foundry.finance.metrics import FinanceMetricProvider
    from foundry.finance.fixtures import build_parker_brads_household

Submodules:
    vocab.py       Finance-owned controlled vocabularies (001 §6) and
                   the additive extensions to Core's vocabularies
    entities.py    Account, Asset, Obligation, Transaction, Valuation,
                   Position, Recurring Series, Tax Jurisdiction,
                   Exchange Rate, Tax Position, Capital Gain Event
                   (001 §7) and their FinanceEntityProjection
    metrics.py     The registered Facts (001 §13, an open set):
                   finance.net_worth, finance.liquidity_runway,
                   finance.cash_flow, finance.asset_allocation,
                   finance.employer_concentration, finance.debt_ratio,
                   finance.cash_available, finance.accessible_assets
    mission_assessment.py
                   Financial Independence policy, low/base/high
                   projection, and MissionAssessment provider
    fixtures.py    The synthetic Parker-Brads household, used by tests
                   and examples/finance_demo.py to validate the pipeline
"""

from .entities import FinanceEntityProjection
from .metrics import FinanceMetricProvider
from .mission_assessment import (
    FinanceProjectionEngine, FinancialIndependenceAssessor,
    FinancialIndependencePolicy,
)
from .missions import (
    FINANCE_MISSION_DEFINITIONS,
    register_finance_mission_definitions,
)
from .mortgage_assessment import (
    MortgageFreedomAssessor,
    MortgageFreedomPolicy,
    MortgageProjectionEngine,
)
from .mortgage_evidence import (
    MortgageEvidenceProjection,
    record_mortgage_evidence,
)

__all__ = [
    "FinanceEntityProjection", "FinanceMetricProvider",
    "FinanceProjectionEngine", "FinancialIndependenceAssessor",
    "FinancialIndependencePolicy", "FINANCE_MISSION_DEFINITIONS",
    "register_finance_mission_definitions", "MortgageFreedomAssessor",
    "MortgageFreedomPolicy", "MortgageProjectionEngine",
    "MortgageEvidenceProjection", "record_mortgage_evidence",
]
