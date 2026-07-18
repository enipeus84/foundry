"""
FinanceMetricProvider — the first five registered Facts
(001-finance-domain-model.md §13).

    finance.net_worth              household-unioned / individually
                                    attributed net worth (001 §9)
    finance.liquidity_runway       liquid + near-liquid holdings over
                                    average essential+committed outflow
    finance.cash_flow              net (or single-category, via
                                    parameters) transaction flow
    finance.asset_allocation       Position value share in one
                                    asset_category (via parameters)
    finance.employer_concentration Position value issued by a scope's
                                    current employer(s), against total

Every calculation is a pure function over `FinanceEntityProjection` (own
state) and a caller-supplied `foundry.core.entities.EntityProjection`
(Party/Employer state, read but never re-derived — 001 §14). No model
call, at any stage (001 §13, design principle 2/§5): an unsupported or
not-yet-observed request returns `status: unsupported`/`unavailable`,
never a guess. `FinanceMetricProvider` implements the `MetricProvider`
Protocol structurally (`000` §13.4) — nothing here is imported by
`foundry.core`; Core reaches this code only via a
`foundry.core.metrics.MetricRegistry` a caller registers it with.

**`as_of` semantics (V1).** Every dated observation is filtered to
`as_of`: transactions by their `ts`, Valuations and Exchange Rates by
their `as_of`, Positions by their `valuation_date` (a Position valued
only after the requested time is excluded, named in `limitations`).
What is *not* reconstructed historically is undated entity state — an
entity's current `status`, ownership links, and revised attributes are
read from the current projection, so a query predating (say) an
account's closure still sees it closed. Point-in-time entity state
requires replaying a truncated log, deferred with the projection engine
(docs/rfc-002-implementation-report.md).

**Projection requests fail closed.** RFC-002 Part 1 implements no
Financial Projection model (001 §16), so a request carrying `horizon`,
`assumption_set_id`, or `scenario_id` returns `status: unsupported` —
answering it with a silently-Baseline number would misrepresent what
was asked (000 §13.4: reject unsupportable shapes *before* attempting
calculation). Likewise a `requested_calculation_version` this provider
cannot reproduce.

Deliberate V1 scope, documented in full in
docs/rfc-002-implementation-report.md:
- Which `ownership_relationship` values confer counted economic value
  (`vocab.VALUE_OWNERSHIP_RELATIONS`) is a product judgement, not a 001
  requirement; `owes` alone counts as a liability, `guarantees` (liable
  only on default) deliberately does not.
- Account "value" = its transaction ledger balance plus the market
  value of Positions held within it; Asset/Obligation "value" = their
  latest applicable Valuation, falling back to Obligation's own
  declared `amount`.
- Transaction flows are attributed to an individual by their ownership
  `share` of the account (001 §9's individual-attribution rule applied
  to flows), so per-member cash flows sum to the household's total.
- Cross-currency aggregation (001 §22) converts via the most recent
  applicable Exchange Rate at or before `as_of`; an item whose currency
  has no such rate is excluded from the total and named in
  `limitations`, rather than failing the whole request closed.
- "Essential + committed monthly outflow" (liquidity runway) is a fixed
  V1 category set (`ESSENTIAL_COMMITTED_CATEGORIES`), not a formula 001
  §13 spells out numerically; refunds in an essential category net
  against spend rather than inflating it.
- `confidence_or_quality` is `"derived"` on every available result —
  Finance's own `tax_estimation_basis` sense of the word: computed
  deterministically from observations, no judgement involved. Never
  arithmetic (000 §13.3).
"""

from __future__ import annotations

import time
from typing import Iterable

from foundry.core.entities import EntityProjection as CoreEntityProjection
from foundry.core.metrics import MetricRequest, MetricResult
from foundry.core.scope import Subject

from . import vocab
from .entities import Account, Asset, FinanceEntityProjection, Obligation

CALCULATION_VERSION = "v1"

METRIC_IDS = frozenset({
    "finance.net_worth",
    "finance.liquidity_runway",
    "finance.cash_flow",
    "finance.asset_allocation",
    "finance.employer_concentration",
})

# A V1 product judgement (see module docstring), not a 001 formula.
ESSENTIAL_COMMITTED_CATEGORIES = frozenset({
    "housing", "transport", "groceries", "childcare", "education",
    "healthcare", "tax_payment",
})

_LIQUID = frozenset({"liquid", "near_liquid"})


class FinanceMetricProvider:
    """Registers `METRIC_IDS` with a `foundry.core.metrics.
    MetricRegistry`. Constructed with the two projections it reads —
    never constructs or rebuilds them itself, so a caller controls
    exactly when each is refreshed. Never appends an event: `calculate`
    is read-only over both projections."""

    def __init__(self, finance_entities: FinanceEntityProjection, core_entities: CoreEntityProjection):
        self.finance = finance_entities
        self.core = core_entities

    def owned_metric_ids(self) -> frozenset[str]:
        return METRIC_IDS

    def calculate(self, request: MetricRequest) -> MetricResult:
        handler = {
            "finance.net_worth": self._net_worth,
            "finance.liquidity_runway": self._liquidity_runway,
            "finance.cash_flow": self._cash_flow,
            "finance.asset_allocation": self._asset_allocation,
            "finance.employer_concentration": self._employer_concentration,
        }.get(request.metric_id)
        if handler is None:
            return self._unsupported(request, "not owned by FinanceMetricProvider")
        if request.horizon is not None or request.assumption_set_id is not None \
                or request.scenario_id is not None:
            return self._unsupported(
                request,
                "Financial Projections (001 §16) are not implemented in RFC-002 "
                "Part 1 — a horizon/assumption_set_id/scenario_id request cannot "
                "be honoured, and a silently-Baseline answer would misrepresent it")
        if request.requested_calculation_version not in (None, CALCULATION_VERSION):
            return self._unsupported(
                request,
                f"calculation_version {request.requested_calculation_version!r} "
                f"cannot be reproduced (current: {CALCULATION_VERSION!r})")
        return handler(request)

    # ------------------------------------------------------------ metrics

    def _net_worth(self, request: MetricRequest) -> MetricResult:
        """(accounts + assets) − owed obligations, unioned by entity id
        for a household scope, share-attributed for a person scope
        (001 §9). Denominated in the household's reporting currency."""
        person_ids = self._scope_persons(request.scope)
        if person_ids is None:
            return self._unsupported(request, "finance.net_worth requires a party scope")
        if not person_ids:
            return self._unavailable(request, "party resolves to no members")

        target = self._target_currency(set(person_ids) | {request.scope.id})
        attribute_to = self._attribute_to(request.scope)
        if attribute_to is None:
            assets, r1, l1 = self._store_total(self.finance.accounts, set(person_ids), target, request.as_of)
            other, r2, l2 = self._store_total(self.finance.assets, set(person_ids), target, request.as_of)
            liabilities, r3, l3 = self._store_total(self.finance.obligations, set(person_ids), target,
                                                      request.as_of, relations=vocab.LIABILITY_RELATIONS)
        else:
            assets, r1, l1 = self._attributed_value(attribute_to, self.finance.accounts, target, request.as_of)
            other, r2, l2 = self._attributed_value(attribute_to, self.finance.assets, target, request.as_of)
            liabilities, r3, l3 = self._attributed_value(attribute_to, self.finance.obligations, target,
                                                           request.as_of, relations=vocab.LIABILITY_RELATIONS)

        refs, limitations = r1 + r2 + r3, l1 + l2 + l3
        if not refs:
            return self._unavailable(request, "no owned accounts, assets, or obligations observed yet",
                                      extra_limitations=limitations)
        return self._available(request, assets + other - liabilities, target, refs, limitations)

    def _liquidity_runway(self, request: MetricRequest) -> MetricResult:
        """liquid + near-liquid holdings (numerator) over average
        essential+committed monthly outflow (denominator), in months.
        Both sides use the same attribution rule: household = union at
        full value, person = share-weighted."""
        person_ids = self._scope_persons(request.scope)
        if person_ids is None:
            return self._unsupported(request, "finance.liquidity_runway requires a party scope")
        if not person_ids:
            return self._unavailable(request, "party resolves to no members")

        target = self._target_currency(set(person_ids) | {request.scope.id})
        attribute_to = self._attribute_to(request.scope)
        if attribute_to is None:
            accounts, r1, l1 = self._store_total(self.finance.accounts, set(person_ids), target,
                                                   request.as_of, filter_liquidity=_LIQUID)
            other, r2, l2 = self._store_total(self.finance.assets, set(person_ids), target,
                                               request.as_of, filter_liquidity=_LIQUID)
        else:
            accounts, r1, l1 = self._attributed_value(attribute_to, self.finance.accounts, target,
                                                        request.as_of, filter_liquidity=_LIQUID)
            other, r2, l2 = self._attributed_value(attribute_to, self.finance.assets, target,
                                                     request.as_of, filter_liquidity=_LIQUID)

        monthly_outflow, r3 = self._average_essential_outflow(
            set(person_ids), attribute_to, target, request.as_of)
        if monthly_outflow is None or monthly_outflow <= 0:
            return self._unavailable(
                request, "no net essential/committed monthly outflow observed yet")

        return self._available(request, (accounts + other) / monthly_outflow, "months",
                                r1 + r2 + r3, l1 + l2)

    def _cash_flow(self, request: MetricRequest) -> MetricResult:
        """Net flow across every owned account's transactions dated at
        or before `as_of` — all categories, or one, via
        `parameters['transaction_category']`. A person scope weights
        each account's flows by that person's ownership share, so
        per-member results sum to the household total (001 §9)."""
        person_ids = self._scope_persons(request.scope)
        if person_ids is None:
            return self._unsupported(request, "finance.cash_flow requires a party scope")
        category = request.parameters.get("transaction_category")
        if category is not None and category not in vocab.TRANSACTION_CATEGORY:
            return self._unsupported(request, f"{category!r} is not a valid transaction_category")

        target = self._target_currency(set(person_ids) | {request.scope.id})
        attribute_to = self._attribute_to(request.scope)
        owned_accounts = self._owned_entities(set(person_ids), self.finance.accounts,
                                               vocab.VALUE_OWNERSHIP_RELATIONS)
        total, refs, limitations, found = 0.0, [], [], False
        for account_id in owned_accounts:
            weight = self._flow_weight(self.finance.accounts[account_id], attribute_to)
            if weight <= 0:
                continue
            for t in self.finance.transactions_in(account_id):
                if t.ts > request.as_of or (category is not None and t.transaction_category != category):
                    continue
                found = True
                converted, conv_ref = self._convert(t.amount, t.currency, target, request.as_of)
                if converted is None:
                    limitations.append(f"no exchange rate {t.currency}->{target} for transaction {t.id}; excluded")
                    continue
                total += converted * weight
                refs.extend(t.provenance)
                if conv_ref:
                    refs.append(conv_ref)
        if not found:
            return self._unavailable(request, "no matching transactions observed yet")
        return self._available(request, total, target, refs, limitations)

    def _asset_allocation(self, request: MetricRequest) -> MetricResult:
        """Market value of Positions in `parameters['asset_category']`
        over the market value of all Positions in owned accounts —
        Positions only; Obligations and non-Position Assets are outside
        this metric's universe by construction (001 §13: "Position by
        asset_category"). Ratios across every category sum to 1 for the
        same scope and as_of."""
        person_ids = self._scope_persons(request.scope)
        if person_ids is None:
            return self._unsupported(request, "finance.asset_allocation requires a party scope")
        category = request.parameters.get("asset_category")
        if category is None:
            return self._unsupported(request, "finance.asset_allocation requires parameters['asset_category']")
        if category not in vocab.ASSET_CATEGORY:
            return self._unsupported(request, f"{category!r} is not a valid asset_category")

        total, category_total, refs, limitations = self._position_totals(
            set(person_ids), request.as_of,
            in_numerator=lambda pos: pos.asset_category == category)
        if total <= 0:
            return self._unavailable(request, "no positions observed yet")
        return self._available(request, category_total / total, "ratio", refs, limitations)

    def _employer_concentration(self, request: MetricRequest) -> MetricResult:
        """Market value of Positions whose `issuer` is a scope member's
        current Employer (their most recent `employed_by` link, 000 §8)
        over the market value of all Positions in owned accounts.
        Identification is by declared Employer id alone — no string
        matching (001 §24, criterion 18). A position counts toward the
        numerator only when its issuer employs an owner of the account
        that holds it."""
        person_ids = self._scope_persons(request.scope)
        if person_ids is None:
            return self._unsupported(request, "finance.employer_concentration requires a party scope")

        employer_of = {}
        for pid in person_ids:
            person = self.core.parties.get(pid)
            if person is not None and person.employers:
                employer_of[pid] = person.employers[-1]  # most recent (000 §8)
        if not employer_of:
            return self._unavailable(request, "no current employer declared for this scope")

        def issued_by_an_owners_employer(pos, owner_ids):
            return pos.issuer in {employer_of[p] for p in owner_ids if p in employer_of}

        total, employer_total, refs, limitations = self._position_totals(
            set(person_ids), request.as_of, in_numerator=issued_by_an_owners_employer,
            numerator_needs_owners=True)
        if total <= 0:
            return self._unavailable(request, "no positions observed yet")
        return self._available(request, employer_total / total, "ratio", refs, limitations)

    # ---------------------------------------------------------------- scope

    def _scope_persons(self, scope: Subject) -> list[str] | None:
        """Household -> its members; person -> itself; anything else
        (Employer, Mission, a bare resource) -> `None`, meaning "this
        metric doesn't know how to resolve this scope shape" — turned
        into `status: unsupported` by the metric."""
        if scope.kind != "party":
            return None
        party = self.core.parties.get(scope.id)
        if party is None:
            return None
        if party.party_type == "household":
            return [m.id for m in self.core.members_of(scope.id)]
        return [scope.id]

    def _attribute_to(self, scope: Subject) -> str | None:
        """`None` for a household scope (union at full value); the
        person's id otherwise (share-weighted attribution, 001 §9)."""
        party = self.core.parties.get(scope.id)
        if party is not None and party.party_type == "household":
            return None
        return scope.id

    def _target_currency(self, party_ids: Iterable[str]) -> str:
        """The Household Party's declared `reporting_currency` (001
        §9, default GBP) — resolved from a direct household scope, or
        from the first household any person in `party_ids` belongs to."""
        parties = [self.core.parties.get(pid) for pid in party_ids]
        for party in parties:
            if party is not None and party.party_type == "household":
                return party.attributes.get("reporting_currency", "GBP")
        for party in parties:
            if party is None:
                continue
            for household_id in party.memberships:
                household = self.core.parties.get(household_id)
                if household is not None:
                    return household.attributes.get("reporting_currency", "GBP")
        return "GBP"

    # ------------------------------------------------------------ ownership

    def _owned_entities(self, person_ids: set[str], store: dict, relations: frozenset[str]) -> dict:
        """`entity_id -> [OwnershipLink, ...]` for every active entity
        in `store` with at least one link in `relations` whose target
        is in `person_ids` — the union-by-entity-id half of 001 §9's
        aggregation rule: an entity co-owned by two scope members
        still appears exactly once here. A link targeting anything
        outside `person_ids` (including, improperly, the household
        Party itself — 001 §9 forbids the group being an ownership
        target) never brings an entity into scope."""
        owned = {}
        for eid, entity in store.items():
            if entity.status != "active":
                continue
            links = [l for l in entity.ownership if l.relation in relations and l.target in person_ids]
            if links:
                owned[eid] = links
        return owned

    def _shares(self, links) -> dict[str, float]:
        """`person_id -> fraction of this entity's value` (001 §9:
        equal split when `share` is omitted, otherwise the declared
        percentage /100). Callers writing co-ownership are responsible
        for declared shares summing to 100% (001 §8) — this function
        does not re-validate that invariant, it only fills gaps left by
        omitted shares."""
        explicit = {l.target: l.share / 100.0 for l in links if l.share is not None}
        implicit = [l.target for l in links if l.share is None]
        if implicit:
            remaining = max(0.0, 1.0 - sum(explicit.values()))
            each = remaining / len(implicit)
            for target in implicit:
                explicit[target] = explicit.get(target, 0.0) + each
        return explicit

    def _flow_weight(self, entity, attribute_to: str | None) -> float:
        """The fraction of an entity's transaction flows attributed to
        the requesting scope: 1.0 for a household union, the person's
        ownership share otherwise — computed from *all* the entity's
        value-ownership links, so a co-owner's fraction is correct even
        though `_owned_entities` pre-filtered links to the scope."""
        if attribute_to is None:
            return 1.0
        links = [l for l in entity.ownership if l.relation in vocab.VALUE_OWNERSHIP_RELATIONS]
        return self._shares(links).get(attribute_to, 0.0)

    # ----------------------------------------------------------- valuation

    def _entity_value(self, entity, as_of: float):
        """`(value, currency, input_refs, limitations)` for one entity
        as of a point in time. `value=None` means "no supportable value"
        — the caller skips it, with the limitation naming why."""
        if isinstance(entity, Account):
            return self._account_value(entity, as_of)
        if isinstance(entity, Asset):
            return self._asset_value(entity, as_of)
        if isinstance(entity, Obligation):
            return self._obligation_value(entity, as_of)
        raise TypeError(f"no value rule for {type(entity)!r}")

    def _account_value(self, account: Account, as_of: float):
        """Ledger balance (sum of transactions dated at or before
        `as_of`) plus the market value of Positions held within it
        (001 §17: a Position is "an investment holding *within* an
        Account"). An empty account is a real £0 balance, anchored to
        the account's own declaration event — distinct from an asset
        with no valuation, whose worth is simply unknown. Position
        currency is assumed to equal its Account's for V1 (documented
        limitation, docs/rfc-002-implementation-report.md)."""
        refs = list(account.provenance)
        limitations = []
        ledger = 0.0
        for t in self.finance.transactions_in(account.id):
            if t.ts > as_of:
                continue
            ledger += t.amount
            refs.extend(t.provenance)
        positions_value = 0.0
        for pos in self.finance.positions_in(account.id):
            if pos.valuation_date > as_of:
                limitations.append(f"position {pos.id} valued only after as_of; excluded")
                continue
            positions_value += pos.market_value
            refs.extend(pos.provenance)
        return ledger + positions_value, account.currency, refs, limitations

    def _asset_value(self, asset: Asset, as_of: float):
        applicable = [v for v in self.finance.valuations_of(asset.id) if v.as_of <= as_of]
        if not applicable:
            reason = ("valued only after as_of" if self.finance.valuations_of(asset.id)
                      else "no valuation observed")
            return None, None, [], [f"asset {asset.id}: {reason}; excluded"]
        latest = max(applicable, key=lambda v: v.as_of)
        return latest.amount, latest.currency, list(latest.provenance), []

    def _obligation_value(self, obligation: Obligation, as_of: float):
        applicable = [v for v in self.finance.valuations_of(obligation.id) if v.as_of <= as_of]
        if applicable:
            latest = max(applicable, key=lambda v: v.as_of)
            return latest.amount, latest.currency, list(latest.provenance), []
        if obligation.amount is not None:
            return obligation.amount, obligation.currency, list(obligation.provenance), []
        return None, None, [], [f"obligation {obligation.id}: no amount or valuation observed; excluded"]

    def _store_total(self, store: dict, person_ids: set[str], target_currency: str, as_of: float,
                      filter_liquidity: frozenset[str] | None = None,
                      relations: frozenset[str] = vocab.VALUE_OWNERSHIP_RELATIONS):
        """Household union: each owned entity once, at full value."""
        owned = self._owned_entities(person_ids, store, relations)
        total, refs, limitations = 0.0, [], []
        for eid in owned:
            entity = store[eid]
            if filter_liquidity is not None and getattr(entity, "liquidity_classification", None) not in filter_liquidity:
                continue
            value, currency, value_refs, value_limits = self._entity_value(entity, as_of)
            limitations.extend(value_limits)
            if value is None:
                continue
            converted, conv_ref = self._convert(value, currency, target_currency, as_of)
            if converted is None:
                limitations.append(f"no exchange rate {currency}->{target_currency} for {eid}; excluded")
                continue
            total += converted
            refs.extend(value_refs)
            if conv_ref:
                refs.append(conv_ref)
        return total, refs, limitations

    def _attributed_value(self, person_id: str, store: dict, target_currency: str, as_of: float,
                           filter_liquidity: frozenset[str] | None = None,
                           relations: frozenset[str] = vocab.VALUE_OWNERSHIP_RELATIONS):
        """Individual attribution: each entity the person holds a
        relevant relation to, at value x their share fraction."""
        total, refs, limitations = 0.0, [], []
        for eid, entity in store.items():
            if entity.status != "active":
                continue
            if filter_liquidity is not None and getattr(entity, "liquidity_classification", None) not in filter_liquidity:
                continue
            links = [l for l in entity.ownership if l.relation in relations]
            if not any(l.target == person_id for l in links):
                continue
            fraction = self._shares(links).get(person_id, 0.0)
            if fraction <= 0:
                continue
            value, currency, value_refs, value_limits = self._entity_value(entity, as_of)
            limitations.extend(value_limits)
            if value is None:
                continue
            converted, conv_ref = self._convert(value, currency, target_currency, as_of)
            if converted is None:
                limitations.append(f"no exchange rate {currency}->{target_currency} for {eid}; excluded")
                continue
            total += converted * fraction
            refs.extend(value_refs)
            if conv_ref:
                refs.append(conv_ref)
        return total, refs, limitations

    def _position_totals(self, person_ids: set[str], as_of: float, in_numerator,
                          numerator_needs_owners: bool = False):
        """`(total, numerator_total, refs, limitations)` over every
        active Position in every owned account, each counted once
        (union by account id, then by position id). Positions valued
        only after `as_of` are excluded and named."""
        owned_accounts = self._owned_entities(person_ids, self.finance.accounts,
                                               vocab.VALUE_OWNERSHIP_RELATIONS)
        total, numerator, refs, limitations = 0.0, 0.0, [], []
        for account_id, links in owned_accounts.items():
            owner_ids = {l.target for l in links}
            for pos in self.finance.positions_in(account_id):
                if pos.valuation_date > as_of:
                    limitations.append(f"position {pos.id} valued only after as_of; excluded")
                    continue
                total += pos.market_value
                refs.extend(pos.provenance)
                matches = (in_numerator(pos, owner_ids) if numerator_needs_owners
                           else in_numerator(pos))
                if matches:
                    numerator += pos.market_value
        return total, numerator, refs, limitations

    # ---------------------------------------------------------------- rates

    def _convert(self, amount: float, currency: str, target: str, as_of: float):
        """Cross-currency aggregation citing the specific Exchange Rate
        event used (001 §22). Returns `(None, None)` — never a guessed
        rate — when no applicable rate has been observed at or before
        `as_of`; a rate dated later never applies retroactively."""
        if currency == target:
            return amount, None
        direct, inverse = f"{currency}/{target}", f"{target}/{currency}"
        candidates = [r for r in self.finance.exchange_rates.values()
                      if r.currency_pair in (direct, inverse) and r.as_of <= as_of]
        if not candidates:
            return None, None
        latest = max(candidates, key=lambda r: r.as_of)
        rate = latest.rate if latest.currency_pair == direct else (1.0 / latest.rate)
        ref = latest.provenance[-1] if latest.provenance else None
        return amount * rate, ref

    def _average_essential_outflow(self, person_ids: set[str], attribute_to: str | None,
                                    target_currency: str, as_of: float):
        """Net essential+committed outflow per distinct calendar month
        observed, share-weighted for a person scope exactly like
        `_cash_flow`. Net, not absolute: a refund in an essential
        category reduces the burn it refunds, rather than inflating it.
        Returns `(None, refs)` when no net outflow is computable."""
        owned_accounts = self._owned_entities(person_ids, self.finance.accounts,
                                               vocab.VALUE_OWNERSHIP_RELATIONS)
        total, refs, months = 0.0, [], set()
        for account_id in owned_accounts:
            weight = self._flow_weight(self.finance.accounts[account_id], attribute_to)
            if weight <= 0:
                continue
            for t in self.finance.transactions_in(account_id):
                if t.ts > as_of or t.transaction_category not in ESSENTIAL_COMMITTED_CATEGORIES:
                    continue
                converted, conv_ref = self._convert(-t.amount, t.currency, target_currency, as_of)
                if converted is None:
                    continue
                total += converted * weight
                refs.extend(t.provenance)
                if conv_ref:
                    refs.append(conv_ref)
                months.add(time.strftime("%Y-%m", time.gmtime(t.ts)))
        if not months or total <= 0:
            return None, refs
        return total / len(months), refs

    # -------------------------------------------------------------- results

    def _available(self, request: MetricRequest, value: float, unit: str,
                    refs: list, limitations: list) -> MetricResult:
        return MetricResult(
            metric_id=request.metric_id, value=value, unit_or_currency=unit,
            scope=request.scope, as_of=request.as_of, status="available",
            calculation_version=CALCULATION_VERSION, input_references=tuple(refs),
            limitations=tuple(limitations), confidence_or_quality="derived",
        )

    def _unavailable(self, request: MetricRequest, reason: str,
                      extra_limitations: list = ()) -> MetricResult:
        """`status: unavailable` — supported in principle, but the
        household hasn't observed enough data yet (001 §5, 000 §7) —
        distinct from `_unsupported`'s "this request shape can never
        be honoured.\""""
        return MetricResult(
            metric_id=request.metric_id, value=None, unit_or_currency=None,
            scope=request.scope, as_of=request.as_of, status="unavailable",
            calculation_version=CALCULATION_VERSION,
            limitations=(reason, *extra_limitations),
        )

    def _unsupported(self, request: MetricRequest, reason: str) -> MetricResult:
        """Provider-level unsupported, carrying this provider's own
        `calculation_version` — per `foundry.core.metrics.unsupported`'s
        docstring, a provider that *has* a meaningful version should
        propagate it even when refusing (the bare core helper's empty
        version means "no provider was reached at all")."""
        return MetricResult(
            metric_id=request.metric_id, value=None, unit_or_currency=None,
            scope=request.scope, as_of=request.as_of, status="unsupported",
            calculation_version=CALCULATION_VERSION, limitations=(reason,),
        )
