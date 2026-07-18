"""
Finance's own entities — 001-finance-domain-model.md §7.

Eleven of the thirteen entities the spec's §7 table lists: Account,
Asset, Obligation, Transaction, Valuation, Position, Recurring Series,
Tax Jurisdiction Configuration, Exchange Rate, Tax Position, Capital
Gain Event. **Assumption Set and Scenario are not implemented here** —
both exist in the spec solely to serve §16's Financial Projection
model, which this package stops short of (see
docs/rfc-002-implementation-report.md).

Every write is `EventLog.append` under a `finance.` event kind, built
from `foundry.core.grammar`'s generic verbs exactly as 001 §3 requires
("Finance then extends and consumes [Core], ... under its own
`finance.*` entities... No parallel finance-specific copies of core
objects"). Every read is `FinanceEntityProjection`, a fold over the log
— a sibling to `foundry.core.entities.EntityProjection`, never a
modification of it, and it never re-derives Party/Employer/Mission
state (001 §14): it folds only `finance.*` events.

**Ownership** (001 §8) uses the `.linked` verb, governed by
`vocab.OWNERSHIP_RELATIONSHIP`, on Account/Asset/Obligation only —
Position is never a direct ownership target; it is "an investment
holding within an Account" (001 §17), so a Position's owner is
resolved transitively through its `account_id`. Because
`grammar.relate()`'s payload shape is fixed to
`{entity_id, relation, target}` and an ownership link may carry an
optional `share` (001 §8), `link_ownership()` below appends directly
via `EventLog.append` rather than calling `grammar.relate()` — the same
sanctioned bypass `foundry.core.evidence.derive_claim_directly()`
already uses when a generic helper's shape doesn't fit a genuine need,
not a parallel primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foundry.eventlog import EventLog

from foundry.core import grammar
from foundry.core import vocab as core_vocab
from . import vocab
from ..errors import VocabularyError

PREFIX = "finance"


# ------------------------------------------------------------------- entities

@dataclass
class OwnershipLink:
    relation: str
    target: str
    share: float | None = None
    event_id: str = ""


@dataclass
class Account:
    id: str
    account_type: str
    currency: str
    name: str | None = None
    tax_wrapper: str = "none"
    liquidity_classification: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)
    ownership: list[OwnershipLink] = field(default_factory=list)


@dataclass
class Asset:
    id: str
    asset_category: str
    currency: str
    name: str | None = None
    liquidity_classification: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)
    ownership: list[OwnershipLink] = field(default_factory=list)


@dataclass
class Obligation:
    id: str
    liability_category: str
    currency: str
    amount: float | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)
    ownership: list[OwnershipLink] = field(default_factory=list)  # `owes`/`guarantees`/`secures` targets


@dataclass
class Transaction:
    id: str
    account_id: str
    amount: float
    currency: str
    transaction_category: str
    ts: float
    description: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class Valuation:
    id: str
    subject_id: str
    amount: float
    currency: str
    as_of: float
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class Position:
    id: str
    account_id: str
    instrument: str
    quantity: float
    unit_price: float
    currency: str
    cost_basis: float
    valuation_date: float
    market_value: float
    asset_category: str
    issuer: str | None = None  # a declared Employer's core id (001 §8)
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class RecurringSeries:
    id: str
    recurring_commitment_type: str
    amount: float
    currency: str
    description: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class TaxJurisdiction:
    id: str
    code: str
    tax_year_start: float
    tax_year_end: float
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class ExchangeRate:
    id: str
    currency_pair: str
    rate: float
    as_of: float
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class TaxPosition:
    id: str
    subject_id: str
    tax_year: str
    jurisdiction_id: str
    estimation_basis: str
    amount: float | None = None
    rule_set_reference: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class CapitalGainEvent:
    id: str
    position_id: str
    realized_gain: float
    currency: str
    date: float
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


# --------------------------------------------------------------- ownership

# The only entity types an ownership relation may attach to (001 §8's
# relation table names no others; a Position's owner is resolved
# transitively through its account_id, 001 §17).
OWNABLE_TYPES = frozenset({"account", "asset", "obligation"})


def link_ownership(log: EventLog, type_: str, entity_id: str, relation: str, target: str,
                    share: float | None = None, actor: str = "user") -> dict:
    """`finance.<type>.linked` for Account/Asset/Obligation ownership
    (001 §8). Both `type_` and `relation` are validated before the
    append — an invalid value must never reach the append-only log.
    See module docstring for why this bypasses `grammar.relate()`."""
    if type_ not in OWNABLE_TYPES:
        raise ValueError(
            f"ownership links attach only to {sorted(OWNABLE_TYPES)} (001 §8), not {type_!r}")
    if relation not in vocab.OWNERSHIP_RELATIONSHIP:
        raise VocabularyError(
            f"{relation!r} is not a valid ownership_relationship "
            f"(known: {sorted(vocab.OWNERSHIP_RELATIONSHIP.values)})")
    if share is not None and not 0.0 < share <= 100.0:
        raise ValueError(f"share must be a percentage in (0, 100], got {share!r}")
    payload: dict[str, Any] = {"entity_id": entity_id, "relation": relation, "target": target}
    if share is not None:
        payload["share"] = share
    return log.append(f"{PREFIX}.{type_}.linked", payload, actor=actor)


# ----------------------------------------------------------------- account

def declare_account(log: EventLog, account_type: str, currency: str, name: str | None = None,
                     tax_wrapper: str = "none", liquidity_classification: str | None = None,
                     actor: str = "user") -> Account:
    if account_type not in vocab.ACCOUNT_TYPE:
        raise VocabularyError(f"{account_type!r} is not a valid account_type")
    if tax_wrapper not in vocab.TAX_WRAPPER:
        raise VocabularyError(f"{tax_wrapper!r} is not a valid tax_wrapper")
    if liquidity_classification is not None and liquidity_classification not in vocab.LIQUIDITY_CLASSIFICATION:
        raise VocabularyError(f"{liquidity_classification!r} is not a valid liquidity_classification")
    account_id = grammar.new_id()
    attrs: dict[str, Any] = {"account_type": account_type, "currency": currency, "tax_wrapper": tax_wrapper}
    if name is not None:
        attrs["name"] = name
    if liquidity_classification is not None:
        attrs["liquidity_classification"] = liquidity_classification
    e = grammar.declare(log, PREFIX, "account", account_id, attrs, actor=actor)
    return Account(id=account_id, account_type=account_type, currency=currency, name=name,
                   tax_wrapper=tax_wrapper, liquidity_classification=liquidity_classification,
                   asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


def close_account(log: EventLog, account_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "account", account_id, reason, actor=actor)


# ------------------------------------------------------------------- asset

def declare_asset(log: EventLog, asset_category: str, currency: str, name: str | None = None,
                   liquidity_classification: str | None = None, actor: str = "user") -> Asset:
    if asset_category not in vocab.ASSET_CATEGORY:
        raise VocabularyError(f"{asset_category!r} is not a valid asset_category")
    if liquidity_classification is not None and liquidity_classification not in vocab.LIQUIDITY_CLASSIFICATION:
        raise VocabularyError(f"{liquidity_classification!r} is not a valid liquidity_classification")
    asset_id = grammar.new_id()
    attrs: dict[str, Any] = {"asset_category": asset_category, "currency": currency}
    if name is not None:
        attrs["name"] = name
    if liquidity_classification is not None:
        attrs["liquidity_classification"] = liquidity_classification
    e = grammar.declare(log, PREFIX, "asset", asset_id, attrs, actor=actor)
    return Asset(id=asset_id, asset_category=asset_category, currency=currency, name=name,
                 liquidity_classification=liquidity_classification, asserted_by=actor,
                 provenance=[e["id"]], history=[e["id"]])


def close_asset(log: EventLog, asset_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "asset", asset_id, reason, actor=actor)


# -------------------------------------------------------------- obligation

def declare_obligation(log: EventLog, liability_category: str, currency: str,
                        amount: float | None = None, actor: str = "user") -> Obligation:
    if liability_category not in vocab.LIABILITY_CATEGORY:
        raise VocabularyError(f"{liability_category!r} is not a valid liability_category")
    obligation_id = grammar.new_id()
    attrs: dict[str, Any] = {"liability_category": liability_category, "currency": currency}
    if amount is not None:
        attrs["amount"] = amount
    e = grammar.declare(log, PREFIX, "obligation", obligation_id, attrs, actor=actor)
    return Obligation(id=obligation_id, liability_category=liability_category, currency=currency,
                       amount=amount, asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


def update_obligation(log: EventLog, obligation_id: str, amount: float, reason: str,
                       actor: str = "user") -> dict:
    return grammar.update(log, PREFIX, "obligation", obligation_id, {"amount": amount}, reason, actor=actor)


def settle_obligation(log: EventLog, obligation_id: str, reason: str = "", actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "obligation", obligation_id, reason, actor=actor, status="settled")


def close_obligation(log: EventLog, obligation_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "obligation", obligation_id, reason, actor=actor, status="closed")


# ------------------------------------------------------------- transaction

def declare_transaction(log: EventLog, account_id: str, amount: float, currency: str,
                         transaction_category: str, ts: float, description: str | None = None,
                         actor: str = "user") -> Transaction:
    if transaction_category not in vocab.TRANSACTION_CATEGORY:
        raise VocabularyError(f"{transaction_category!r} is not a valid transaction_category")
    txn_id = grammar.new_id()
    attrs: dict[str, Any] = {"account_id": account_id, "amount": amount, "currency": currency,
                              "transaction_category": transaction_category, "ts": ts}
    if description is not None:
        attrs["description"] = description
    e = grammar.declare(log, PREFIX, "transaction", txn_id, attrs, actor=actor)
    return Transaction(id=txn_id, account_id=account_id, amount=amount, currency=currency,
                        transaction_category=transaction_category, ts=ts, description=description,
                        asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


def correct_transaction(log: EventLog, transaction_id: str, reason: str,
                         actor: str = "user", **changes: Any) -> dict:
    """`finance.transaction.corrected` (001 §11) — literally
    `finance.transaction.updated` with a mandatory `reason`, which
    `grammar.update()` already requires positionally. A corrected
    `transaction_category` is re-validated: the correction path must
    not be a loophole through which an ungoverned value reaches the
    append-only log."""
    if "transaction_category" in changes and changes["transaction_category"] not in vocab.TRANSACTION_CATEGORY:
        raise VocabularyError(f"{changes['transaction_category']!r} is not a valid transaction_category")
    return grammar.update(log, PREFIX, "transaction", transaction_id, changes, reason, actor=actor)


# --------------------------------------------------------------- valuation

def declare_valuation(log: EventLog, subject_id: str, amount: float, currency: str, as_of: float,
                       actor: str = "user") -> Valuation:
    """A point-in-time worth assertion (001 §7) against any Finance
    entity id — most often an Account or Asset. Valuation has no
    `.updated`/`.closed`: a revised worth is a new Valuation event, not
    a mutation of the old one — the old assertion remains true of the
    moment it described."""
    valuation_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "valuation", valuation_id, {
        "subject_id": subject_id, "amount": amount, "currency": currency, "as_of": as_of,
    }, actor=actor)
    return Valuation(id=valuation_id, subject_id=subject_id, amount=amount, currency=currency,
                      as_of=as_of, asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


# ---------------------------------------------------------------- position

def declare_position(log: EventLog, account_id: str, instrument: str, quantity: float,
                      unit_price: float, currency: str, cost_basis: float, valuation_date: float,
                      market_value: float, asset_category: str, issuer: str | None = None,
                      actor: str = "user") -> Position:
    if asset_category not in vocab.ASSET_CATEGORY:
        raise VocabularyError(f"{asset_category!r} is not a valid asset_category")
    position_id = grammar.new_id()
    attrs: dict[str, Any] = {
        "account_id": account_id, "instrument": instrument, "quantity": quantity,
        "unit_price": unit_price, "currency": currency, "cost_basis": cost_basis,
        "valuation_date": valuation_date, "market_value": market_value,
        "asset_category": asset_category,
    }
    if issuer is not None:
        attrs["issuer"] = issuer
    e = grammar.declare(log, PREFIX, "position", position_id, attrs, actor=actor)
    return Position(id=position_id, account_id=account_id, instrument=instrument, quantity=quantity,
                     unit_price=unit_price, currency=currency, cost_basis=cost_basis,
                     valuation_date=valuation_date, market_value=market_value,
                     asset_category=asset_category, issuer=issuer, asserted_by=actor,
                     provenance=[e["id"]], history=[e["id"]])


def update_position(log: EventLog, position_id: str, reason: str, actor: str = "user",
                     **changes: Any) -> dict:
    return grammar.update(log, PREFIX, "position", position_id, changes, reason, actor=actor)


def close_position(log: EventLog, position_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "position", position_id, reason, actor=actor)


# --------------------------------------------------------- recurring series

def declare_recurring_series(log: EventLog, recurring_commitment_type: str, amount: float,
                              currency: str, description: str | None = None,
                              actor: str = "user") -> RecurringSeries:
    """Describes an *expected* future pattern (001 §15) — it never
    pre-creates a canonical `finance.transaction.declared` event."""
    if recurring_commitment_type not in vocab.RECURRING_COMMITMENT_TYPE:
        raise VocabularyError(f"{recurring_commitment_type!r} is not a valid recurring_commitment_type")
    series_id = grammar.new_id()
    attrs: dict[str, Any] = {"recurring_commitment_type": recurring_commitment_type,
                              "amount": amount, "currency": currency}
    if description is not None:
        attrs["description"] = description
    e = grammar.declare(log, PREFIX, "recurring_series", series_id, attrs, actor=actor)
    return RecurringSeries(id=series_id, recurring_commitment_type=recurring_commitment_type,
                            amount=amount, currency=currency, description=description,
                            asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


def pause_recurring_series(log: EventLog, series_id: str, reason: str, actor: str = "user") -> dict:
    """Not terminal — `.updated`, not `.closed`, since a paused series
    may later resume."""
    return grammar.update(log, PREFIX, "recurring_series", series_id, {"status": "paused"}, reason, actor=actor)


def resume_recurring_series(log: EventLog, series_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.update(log, PREFIX, "recurring_series", series_id, {"status": "active"}, reason, actor=actor)


def end_recurring_series(log: EventLog, series_id: str, reason: str = "", actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "recurring_series", series_id, reason, actor=actor, status="ended")


# ----------------------------------------------------------- fulfils (§8, §15)

def fulfil(log: EventLog, transaction_id: str, series_id: str, actor: str = "user") -> dict:
    """A Transaction relates to the Recurring Series it satisfies —
    Finance's additive `fulfils` value on `structural_relationship`
    (001 §6). Uses Core's own `grammar.relate()` unmodified: `fulfils`
    lives in `foundry.core.vocab.STRUCTURAL_RELATIONSHIP` because this
    module imports `finance.vocab`, whose module-level `.extend()` call
    registers it."""
    return grammar.relate(log, PREFIX, "transaction", transaction_id, "fulfils", series_id,
                           core_vocab.STRUCTURAL_RELATIONSHIP, actor=actor)


# ------------------------------------------------------------ tax jurisdiction

def declare_tax_jurisdiction(log: EventLog, code: str, tax_year_start: float, tax_year_end: float,
                              actor: str = "user") -> TaxJurisdiction:
    jurisdiction_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "tax_jurisdiction", jurisdiction_id, {
        "code": code, "tax_year_start": tax_year_start, "tax_year_end": tax_year_end,
    }, actor=actor)
    return TaxJurisdiction(id=jurisdiction_id, code=code, tax_year_start=tax_year_start,
                            tax_year_end=tax_year_end, asserted_by=actor,
                            provenance=[e["id"]], history=[e["id"]])


def update_tax_jurisdiction(log: EventLog, jurisdiction_id: str, reason: str, actor: str = "user",
                             **changes: Any) -> dict:
    return grammar.update(log, PREFIX, "tax_jurisdiction", jurisdiction_id, changes, reason, actor=actor)


def tax_resident_in(log: EventLog, party_id: str, jurisdiction_id: str, actor: str = "user") -> dict:
    """Person/Household -> Tax Jurisdiction Configuration (001 §19),
    Finance's additive value on Core's `party_relationship`. Written
    against the *Party's* own `core.party.*` stream (001 §3: no
    parallel finance-prefixed shadow of a Core entity's relations)."""
    return grammar.relate(log, "core", "party", party_id, "tax_resident_in", jurisdiction_id,
                           core_vocab.PARTY_RELATIONSHIP, actor=actor)


# ------------------------------------------------------------- exchange rate

def declare_exchange_rate(log: EventLog, currency_pair: str, rate: float, as_of: float,
                           actor: str = "user") -> ExchangeRate:
    """V1 uses `.declared` only (001 §11) — a revised rate is a new,
    separately dated observation, not a mutation of an old one."""
    rate_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "exchange_rate", rate_id, {
        "currency_pair": currency_pair, "rate": rate, "as_of": as_of,
    }, actor=actor)
    return ExchangeRate(id=rate_id, currency_pair=currency_pair, rate=rate, as_of=as_of,
                         asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


# --------------------------------------------------------------- tax position

def declare_tax_position(log: EventLog, subject_id: str, tax_year: str, jurisdiction_id: str,
                          estimation_basis: str, amount: float | None = None,
                          rule_set_reference: str | None = None, actor: str = "user") -> TaxPosition:
    """`estimation_basis` is never optional (001 §5, design principle
    2): an unsupported calculation produces no `amount` rather than a
    guess, enforced here — not left to caller discipline."""
    if estimation_basis not in vocab.TAX_ESTIMATION_BASIS:
        raise VocabularyError(f"{estimation_basis!r} is not a valid tax_estimation_basis")
    if estimation_basis == "unsupported" and amount is not None:
        raise ValueError("an unsupported Tax Position must not carry an amount")
    position_id = grammar.new_id()
    attrs: dict[str, Any] = {
        "subject_id": subject_id, "tax_year": tax_year, "jurisdiction_id": jurisdiction_id,
        "estimation_basis": estimation_basis,
    }
    if amount is not None:
        attrs["amount"] = amount
    if rule_set_reference is not None:
        attrs["rule_set_reference"] = rule_set_reference
    e = grammar.declare(log, PREFIX, "tax_position", position_id, attrs, actor=actor)
    status = "unsupported" if estimation_basis == "unsupported" else "active"
    return TaxPosition(id=position_id, subject_id=subject_id, tax_year=tax_year,
                        jurisdiction_id=jurisdiction_id, estimation_basis=estimation_basis,
                        amount=amount, rule_set_reference=rule_set_reference, status=status,
                        asserted_by=actor, provenance=[e["id"]], history=[e["id"]])


def supersede_tax_position(log: EventLog, tax_position_id: str, reason: str, actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "tax_position", tax_position_id, reason, actor=actor, status="superseded")


# --------------------------------------------------------- capital gain event

def declare_capital_gain_event(log: EventLog, position_id: str, realized_gain: float, currency: str,
                                date: float, actor: str = "user") -> CapitalGainEvent:
    """No `.closed` state exists for this entity (001 §11) — a realised
    gain or loss is a fact about a completed disposal, not something
    with a further lifecycle."""
    event_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "capital_gain_event", event_id, {
        "position_id": position_id, "realized_gain": realized_gain,
        "currency": currency, "date": date,
    }, actor=actor)
    return CapitalGainEvent(id=event_id, position_id=position_id, realized_gain=realized_gain,
                             currency=currency, date=date, asserted_by=actor,
                             provenance=[e["id"]], history=[e["id"]])


# ---------------------------------------------------------------------- reads

class FinanceEntityProjection:
    """Current state for Finance's eleven entity types, folded only
    from `finance.*` events (001 §14). Deletable and rebuildable, with
    no write path of its own; `apply()` is the incremental
    optimisation, `rebuild()` the correctness oracle they must always
    agree with — the same regression discipline `Canon` and
    `foundry.core.entities.EntityProjection` already establish.

    Never folds `core.*` or `claim.*` events: Party/Employer/Mission
    state is read from a caller-supplied `foundry.core.entities.
    EntityProjection` instead (001 §14), never re-derived here."""

    def __init__(self, log: EventLog):
        self.log = log
        self.accounts: dict[str, Account] = {}
        self.assets: dict[str, Asset] = {}
        self.obligations: dict[str, Obligation] = {}
        self.transactions: dict[str, Transaction] = {}
        self.valuations: dict[str, Valuation] = {}
        self.positions: dict[str, Position] = {}
        self.recurring_series: dict[str, RecurringSeries] = {}
        self.tax_jurisdictions: dict[str, TaxJurisdiction] = {}
        self.exchange_rates: dict[str, ExchangeRate] = {}
        self.tax_positions: dict[str, TaxPosition] = {}
        self.capital_gain_events: dict[str, CapitalGainEvent] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.accounts, self.assets, self.obligations = {}, {}, {}
        self.transactions, self.valuations, self.positions = {}, {}, {}
        self.recurring_series, self.tax_jurisdictions = {}, {}
        self.exchange_rates, self.tax_positions, self.capital_gain_events = {}, {}, {}
        for e in self.log.events():
            self.apply(e)

    def apply(self, e: dict) -> None:
        kind = e["kind"]
        if not kind.startswith(f"{PREFIX}."):
            return  # core.*, claim.*, ingest — not this projection's concern
        type_ = kind.split(".")[1]
        handler = {
            "account": self._apply_account, "asset": self._apply_asset,
            "obligation": self._apply_obligation, "transaction": self._apply_transaction,
            "valuation": self._apply_valuation, "position": self._apply_position,
            "recurring_series": self._apply_recurring_series,
            "tax_jurisdiction": self._apply_tax_jurisdiction,
            "exchange_rate": self._apply_exchange_rate,
            "tax_position": self._apply_tax_position,
            "capital_gain_event": self._apply_capital_gain_event,
        }.get(type_)
        if handler:
            handler(e)

    def valuations_of(self, subject_id: str) -> list[Valuation]:
        """Every Valuation asserted against a subject, in log order —
        the caller picks "latest by as_of" or any other policy; this
        projection has no opinion on which valuation is current."""
        return [v for v in self.valuations.values() if v.subject_id == subject_id]

    def positions_in(self, account_id: str) -> list[Position]:
        return [p for p in self.positions.values()
                if p.account_id == account_id and p.status == "active"]

    def transactions_in(self, account_id: str) -> list[Transaction]:
        return [t for t in self.transactions.values() if t.account_id == account_id]

    # -------------------------------------------------------- internals

    def _apply_account(self, e: dict) -> None:
        self._apply_ownership_entity(e, self.accounts, Account, {
            "account_type", "currency", "name", "tax_wrapper", "liquidity_classification"})

    def _apply_asset(self, e: dict) -> None:
        self._apply_ownership_entity(e, self.assets, Asset, {
            "asset_category", "currency", "name", "liquidity_classification"})

    def _apply_obligation(self, e: dict) -> None:
        self._apply_ownership_entity(e, self.obligations, Obligation, {"liability_category", "currency", "amount"})

    def _apply_ownership_entity(self, e: dict, store: dict, cls, updatable_fields: set[str]) -> None:
        """Shared fold for the three entity types that can carry
        ownership links (Account, Asset, Obligation) — declared/
        updated/closed/linked all behave identically across the three;
        only the dataclass and its declared-time attribute set differ."""
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        eid = p["entity_id"]
        if verb == "declared":
            kwargs = {k: p.get(k) for k in updatable_fields if k in p}
            store[eid] = cls(id=eid, asserted_by=e["actor"], provenance=[e["id"]],
                              history=[e["id"]], **kwargs)
        elif verb == "updated":
            entity = store.get(eid)
            if entity:
                for k, v in p.items():
                    if k in updatable_fields:
                        setattr(entity, k, v)
                entity.history.append(e["id"])
        elif verb == "closed":
            entity = store.get(eid)
            if entity:
                entity.status = p.get("status", "closed")
                entity.history.append(e["id"])
        elif verb == "linked":
            entity = store.get(eid)
            if entity:
                entity.ownership.append(OwnershipLink(
                    relation=p["relation"], target=p["target"], share=p.get("share"), event_id=e["id"]))
                entity.history.append(e["id"])

    def _apply_transaction(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        tid = p["entity_id"]
        if verb == "declared":
            self.transactions[tid] = Transaction(
                id=tid, account_id=p["account_id"], amount=p["amount"], currency=p["currency"],
                transaction_category=p["transaction_category"], ts=p["ts"],
                description=p.get("description"), asserted_by=e["actor"],
                provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "updated":
            # finance.transaction.corrected is finance.transaction.updated (001 §11):
            # a correction always moves status to "corrected".
            t = self.transactions.get(tid)
            if t:
                for k in ("amount", "currency", "transaction_category", "ts", "description"):
                    if k in p:
                        setattr(t, k, p[k])
                t.status = "corrected"
                t.history.append(e["id"])

    def _apply_valuation(self, e: dict) -> None:
        p = e["payload"]
        vid = p["entity_id"]
        self.valuations[vid] = Valuation(
            id=vid, subject_id=p["subject_id"], amount=p["amount"], currency=p["currency"],
            as_of=p["as_of"], asserted_by=e["actor"], provenance=[e["id"]], history=[e["id"]],
        )

    def _apply_position(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        pid = p["entity_id"]
        if verb == "declared":
            self.positions[pid] = Position(
                id=pid, account_id=p["account_id"], instrument=p["instrument"],
                quantity=p["quantity"], unit_price=p["unit_price"], currency=p["currency"],
                cost_basis=p["cost_basis"], valuation_date=p["valuation_date"],
                market_value=p["market_value"], asset_category=p["asset_category"],
                issuer=p.get("issuer"), asserted_by=e["actor"],
                provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "updated":
            pos = self.positions.get(pid)
            if pos:
                for k in ("quantity", "unit_price", "cost_basis", "valuation_date",
                          "market_value", "issuer"):
                    if k in p:
                        setattr(pos, k, p[k])
                pos.history.append(e["id"])
        elif verb == "closed":
            pos = self.positions.get(pid)
            if pos:
                pos.status = "closed"
                pos.history.append(e["id"])

    def _apply_recurring_series(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        sid = p["entity_id"]
        if verb == "declared":
            self.recurring_series[sid] = RecurringSeries(
                id=sid, recurring_commitment_type=p["recurring_commitment_type"],
                amount=p["amount"], currency=p["currency"], description=p.get("description"),
                asserted_by=e["actor"], provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "updated":
            s = self.recurring_series.get(sid)
            if s and "status" in p:
                s.status = p["status"]
                s.history.append(e["id"])
        elif verb == "closed":
            s = self.recurring_series.get(sid)
            if s:
                s.status = p.get("status", "ended")
                s.history.append(e["id"])

    def _apply_tax_jurisdiction(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        jid = p["entity_id"]
        if verb == "declared":
            self.tax_jurisdictions[jid] = TaxJurisdiction(
                id=jid, code=p["code"], tax_year_start=p["tax_year_start"],
                tax_year_end=p["tax_year_end"], asserted_by=e["actor"],
                provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "updated":
            j = self.tax_jurisdictions.get(jid)
            if j:
                for k in ("code", "tax_year_start", "tax_year_end"):
                    if k in p:
                        setattr(j, k, p[k])
                j.history.append(e["id"])

    def _apply_exchange_rate(self, e: dict) -> None:
        p = e["payload"]
        rid = p["entity_id"]
        self.exchange_rates[rid] = ExchangeRate(
            id=rid, currency_pair=p["currency_pair"], rate=p["rate"], as_of=p["as_of"],
            asserted_by=e["actor"], provenance=[e["id"]], history=[e["id"]],
        )

    def _apply_tax_position(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        tid = p["entity_id"]
        if verb == "declared":
            basis = p["estimation_basis"]
            self.tax_positions[tid] = TaxPosition(
                id=tid, subject_id=p["subject_id"], tax_year=p["tax_year"],
                jurisdiction_id=p["jurisdiction_id"], estimation_basis=basis,
                amount=p.get("amount"), rule_set_reference=p.get("rule_set_reference"),
                status="unsupported" if basis == "unsupported" else "active",
                asserted_by=e["actor"], provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "closed":
            t = self.tax_positions.get(tid)
            if t:
                t.status = p.get("status", "superseded")
                t.history.append(e["id"])

    def _apply_capital_gain_event(self, e: dict) -> None:
        p = e["payload"]
        cid = p["entity_id"]
        self.capital_gain_events[cid] = CapitalGainEvent(
            id=cid, position_id=p["position_id"], realized_gain=p["realized_gain"],
            currency=p["currency"], date=p["date"], asserted_by=e["actor"],
            provenance=[e["id"]], history=[e["id"]],
        )
