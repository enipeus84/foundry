"""Read-only household authority for RFC-017 Value Provenance.

The composition root supplies snapshots from canonical Core projections. This
module intentionally imports neither registry nor event machinery: the resolver
needs one narrow authority answer, not registry or writer capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from .scope import Subject


class SubjectAuthority(Protocol):
    """Read-only mapping from a value subject to its authorising household."""

    def household_for(self, subject: Subject) -> str | None: ...


@dataclass(frozen=True)
class CanonicalSubjectAuthority:
    """A read-only authority snapshot assembled from Core canonical state.

    ``asset_registrations`` and ``parties`` are read views of canonical Core
    projections. Their values are deliberately duck-typed at this seam so
    Value Provenance has no registry or event-writer dependency.
    """

    _party_households: Mapping[str, str]
    _resource_households: Mapping[str, str]

    @classmethod
    def from_canonical_state(cls, *, asset_registrations: Mapping[str, object],
                             parties: Mapping[str, object]) -> CanonicalSubjectAuthority:
        household_ids = {
            party_id
            for party_id, party in parties.items()
            if (isinstance(party_id, str)
                and getattr(party, "party_type", None) == "household"
                and getattr(party, "status", None) == "active")
        }
        party_households = {party_id: party_id for party_id in household_ids}
        for party_id, party in parties.items():
            memberships = {
                household_id
                for household_id in getattr(party, "memberships", ())
                if household_id in household_ids
            }
            if (isinstance(party_id, str)
                    and getattr(party, "party_type", None) == "person"
                    and getattr(party, "status", None) == "active"
                    and len(memberships) == 1):
                party_households[party_id] = next(iter(memberships))
        resource_households = {
            subject_id: registration.household_id
            for subject_id, registration in asset_registrations.items()
            if (isinstance(subject_id, str)
                and isinstance(getattr(registration, "household_id", None), str)
                and registration.household_id in household_ids)
        }
        return cls(MappingProxyType(party_households), MappingProxyType(resource_households))

    def household_for(self, subject: Subject) -> str | None:
        if subject.kind == "party":
            return self._party_households.get(subject.id)
        return self._resource_households.get(subject.id)
