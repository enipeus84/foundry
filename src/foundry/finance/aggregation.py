"""Supported Finance-internal scope, ownership and currency helpers.

This service owns the aggregation rules shared by Finance metric and mission
providers.  It remains inside Finance: Core supplies projections and scope
types but does not learn Finance ownership or exchange-rate semantics.
"""

from __future__ import annotations

from typing import Iterable

from foundry.core.entities import EntityProjection as CoreEntityProjection
from foundry.core.scope import Subject

from . import vocab
from .entities import FinanceEntityProjection


class FinanceAggregationService:
    """Read-only Finance aggregation operations over caller-owned projections."""

    def __init__(
        self,
        finance: FinanceEntityProjection,
        core: CoreEntityProjection,
    ):
        self.finance = finance
        self.core = core

    def persons_for_scope(self, scope: Subject) -> list[str] | None:
        """Resolve a Party scope to household members or the person itself."""
        if scope.kind != "party":
            return None
        party = self.core.parties.get(scope.id)
        if party is None:
            return None
        if party.party_type == "household":
            return [member.id for member in self.core.members_of(scope.id)]
        return [scope.id]

    def attribute_to(self, scope: Subject) -> str | None:
        """Return the individual attribution target, or none for a household."""
        party = self.core.parties.get(scope.id)
        if party is not None and party.party_type == "household":
            return None
        return scope.id

    def target_currency(self, party_ids: Iterable[str]) -> str:
        """Resolve the household reporting currency, defaulting to GBP."""
        parties = [self.core.parties.get(party_id) for party_id in party_ids]
        for party in parties:
            if party is not None and party.party_type == "household":
                return party.attributes.get("reporting_currency", "GBP")
        for party in parties:
            if party is None:
                continue
            for household_id in party.memberships:
                household = self.core.parties.get(household_id)
                if household is not None:
                    return household.attributes.get(
                        "reporting_currency", "GBP")
        return "GBP"

    @staticmethod
    def owned_entities(
        person_ids: set[str],
        store: dict,
        relations: frozenset[str],
    ) -> dict:
        """Return each active, in-scope entity once with its matching links."""
        owned = {}
        for entity_id, entity in store.items():
            if entity.status != "active":
                continue
            links = [
                link for link in entity.ownership
                if link.relation in relations and link.target in person_ids
            ]
            if links:
                owned[entity_id] = links
        return owned

    @staticmethod
    def shares(links) -> dict[str, float]:
        """Resolve declared or equal-split ownership shares as fractions."""
        explicit = {
            link.target: link.share / 100.0
            for link in links if link.share is not None
        }
        implicit = [link.target for link in links if link.share is None]
        if implicit:
            remaining = max(0.0, 1.0 - sum(explicit.values()))
            each = remaining / len(implicit)
            for target in implicit:
                explicit[target] = explicit.get(target, 0.0) + each
        return explicit

    def flow_weight(self, entity, attribute_to: str | None) -> float:
        """Resolve the transaction-flow share for a household or person."""
        if attribute_to is None:
            return 1.0
        links = [
            link for link in entity.ownership
            if link.relation in vocab.VALUE_OWNERSHIP_RELATIONS
        ]
        return self.shares(links).get(attribute_to, 0.0)

    def convert(
        self,
        amount: float,
        currency: str,
        target: str,
        as_of: float,
    ) -> tuple[float | None, str | None]:
        """Convert with the latest applicable observed rate, never a guess."""
        if currency == target:
            return amount, None
        direct, inverse = f"{currency}/{target}", f"{target}/{currency}"
        candidates = [
            rate for rate in self.finance.exchange_rates.values()
            if rate.currency_pair in (direct, inverse)
            and rate.as_of <= as_of
            and rate.rate > 0
        ]
        if not candidates:
            return None, None
        latest = max(candidates, key=lambda rate: rate.as_of)
        rate = (
            latest.rate
            if latest.currency_pair == direct
            else 1.0 / latest.rate
        )
        reference = latest.provenance[-1] if latest.provenance else None
        return amount * rate, reference
