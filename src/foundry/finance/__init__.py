"""
Foundry Finance — the first product domain built on Core
(docs/specifications/001-finance-domain-model.md).

RFC-002, Part 1: deterministic entities and the first five registered
metrics, validated against a synthetic household fixture. It stops
before `002 §16 (Financial Projection model)` — Assumption Set and
Scenario are not implemented in this package; see
`docs/rfc-002-implementation-report.md` for what's deferred and why.

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
                   finance.cash_available
    fixtures.py    The synthetic Parker-Brads household, used by tests
                   and examples/finance_demo.py to validate the pipeline
"""

from .entities import FinanceEntityProjection
from .metrics import FinanceMetricProvider

__all__ = ["FinanceEntityProjection", "FinanceMetricProvider"]
