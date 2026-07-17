"""
Party, Employer, Mission — 000-core-domain-model.md §8.

Three domain-agnostic entities, each a projection over `core.*` events,
in exactly the shape `canon.Claim` already establishes: an identity, a
status lifecycle, provenance back to the event(s) that justify it, and
full history. `EntityProjection` is a fold over the log — a sibling to
`Canon`, never a modification of it (000 §5, principle 1) — deletable
and rebuildable, with no write path of its own.

A shared entity has exactly one canonical event stream (000 §5,
principle 3): a dependent domain that needs to attach its own attribute
to a Party (Finance's `reporting_currency` on the Household Party) calls
`update_party` on the *same* `core.party.*` stream — there is no
domain-prefixed shadow to create.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foundry.eventlog import EventLog

from . import grammar, vocab
from ..errors import VocabularyError

PREFIX = "core"


@dataclass
class Party:
    id: str
    party_type: str
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    memberships: list[str] = field(default_factory=list)   # household Party ids
    employers: list[str] = field(default_factory=list)      # Employer ids, most recent last


@dataclass
class Employer:
    id: str
    name: str
    industry: str | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


@dataclass
class Mission:
    id: str
    name: str
    target_metric: str = ""
    target_value: float | None = None
    target_range: tuple[float, float] | None = None
    target_date: float | None = None
    tolerance: float | None = None
    status: str = "active"
    provenance: list[str] = field(default_factory=list)
    asserted_by: str = ""
    history: list[str] = field(default_factory=list)


# --------------------------------------------------------------- writes

def declare_party(log: EventLog, party_type: str, actor: str = "user") -> Party:
    """`party_type` is validated against `vocab.PARTY_TYPE`
    (`VocabularyError` if it isn't `"person"`/`"household"` or a
    domain-registered extension) before anything is written."""
    if party_type not in vocab.PARTY_TYPE:
        raise VocabularyError(f"{party_type!r} is not a valid party_type")
    party_id = grammar.new_id()
    e = grammar.declare(log, PREFIX, "party", party_id, {"party_type": party_type}, actor=actor)
    return Party(id=party_id, party_type=party_type, asserted_by=actor,
                 provenance=[e["id"]], history=[e["id"]])


def update_party(log: EventLog, party_id: str, changes: dict[str, Any],
                  reason: str, actor: str = "user") -> dict:
    """The one canonical stream a dependent domain writes to when it
    needs to attach its own attribute to a Party (000 §5, principle 3)."""
    return grammar.update(log, PREFIX, "party", party_id, changes, reason, actor=actor)


def close_party(log: EventLog, party_id: str, reason: str, actor: str = "user") -> dict:
    """Generic closure only — unlike Mission, Party has no distinct
    terminal sub-states to record, so no `status` extra is written."""
    return grammar.close(log, PREFIX, "party", party_id, reason, actor=actor)


def join_household(log: EventLog, person_party_id: str, household_party_id: str,
                    actor: str = "user") -> dict:
    """The `member_of` link is directional: `person_party_id` is the
    member, `household_party_id` is the group — reversing the two
    arguments silently produces a nonsensical link (a household
    'joining' a person) rather than an error, since Core has no way to
    tell the two `party_type` values apart from a bare id."""
    return grammar.relate(log, PREFIX, "party", person_party_id, "member_of",
                           household_party_id, vocab.PARTY_RELATIONSHIP, actor=actor)


def declare_employer(log: EventLog, name: str, industry: str | None = None,
                      actor: str = "user") -> Employer:
    employer_id = grammar.new_id()
    attrs: dict[str, Any] = {"name": name}
    if industry is not None:
        attrs["industry"] = industry
    e = grammar.declare(log, PREFIX, "employer", employer_id, attrs, actor=actor)
    return Employer(id=employer_id, name=name, industry=industry, asserted_by=actor,
                     provenance=[e["id"]], history=[e["id"]])


def close_employer(log: EventLog, employer_id: str, reason: str, actor: str = "user") -> dict:
    """No `status_vocabulary` here, unlike `achieve_mission`/
    `abandon_mission`: `"defunct"` is Employer's one terminal state
    (000 §8's entity table), not one of `000` §7's controlled
    vocabularies — there is nothing to validate `status` against."""
    return grammar.close(log, PREFIX, "employer", employer_id, reason, actor=actor, status="defunct")


def employ(log: EventLog, person_party_id: str, employer_id: str, actor: str = "user") -> dict:
    return grammar.relate(log, PREFIX, "party", person_party_id, "employed_by",
                           employer_id, vocab.PARTY_RELATIONSHIP, actor=actor)


def declare_mission(log: EventLog, name: str, target_metric: str = "",
                     target_value: float | None = None,
                     target_range: tuple[float, float] | None = None,
                     target_date: float | None = None,
                     tolerance: float | None = None, actor: str = "user") -> Mission:
    mission_id = grammar.new_id()
    attrs = {
        "name": name, "target_metric": target_metric, "target_value": target_value,
        "target_range": list(target_range) if target_range else None,
        "target_date": target_date, "tolerance": tolerance,
    }
    e = grammar.declare(log, PREFIX, "mission", mission_id, attrs, actor=actor)
    return Mission(id=mission_id, name=name, target_metric=target_metric,
                    target_value=target_value,
                    target_range=tuple(target_range) if target_range else None,
                    target_date=target_date, tolerance=tolerance, asserted_by=actor,
                    provenance=[e["id"]], history=[e["id"]])


def achieve_mission(log: EventLog, mission_id: str, reason: str = "", actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "mission", mission_id, reason, actor=actor,
                          status="achieved", status_vocabulary=vocab.MISSION_STATUS)


def abandon_mission(log: EventLog, mission_id: str, reason: str = "", actor: str = "user") -> dict:
    return grammar.close(log, PREFIX, "mission", mission_id, reason, actor=actor,
                          status="abandoned", status_vocabulary=vocab.MISSION_STATUS)


# ---------------------------------------------------------------- reads

class EntityProjection:
    """Current Party/Employer/Mission state, folded from `core.*`
    events. `apply()` is the incremental optimisation; `rebuild()` is
    the correctness oracle they must always agree with (mirrors
    `Canon`'s own regression discipline)."""

    def __init__(self, log: EventLog):
        self.log = log
        self.parties: dict[str, Party] = {}
        self.employers: dict[str, Employer] = {}
        self.missions: dict[str, Mission] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.parties, self.employers, self.missions = {}, {}, {}
        for e in self.log.events():
            self.apply(e)

    def apply(self, e: dict) -> None:
        kind = e["kind"]
        if kind.startswith("core.party."):
            self._apply_party(e)
        elif kind.startswith("core.employer."):
            self._apply_employer(e)
        elif kind.startswith("core.mission."):
            self._apply_mission(e)
        # Everything else (finance.*, claim.*, ingest) is silently
        # ignored — the same fallthrough discipline Canon already uses.

    def members_of(self, household_party_id: str) -> list[Party]:
        return [p for p in self.parties.values()
                if p.party_type == "person" and household_party_id in p.memberships]

    # -------------------------------------------------------- internals

    def _apply_party(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        pid = p["entity_id"]
        if verb == "declared":
            self.parties[pid] = Party(id=pid, party_type=p["party_type"], asserted_by=e["actor"],
                                       provenance=[e["id"]], history=[e["id"]])
        elif verb == "updated":
            party = self.parties.get(pid)
            if party:
                for k, v in p.items():
                    if k not in ("entity_id", "reason"):
                        party.attributes[k] = v
                party.history.append(e["id"])
        elif verb == "closed":
            party = self.parties.get(pid)
            if party:
                party.status = "closed"
                party.history.append(e["id"])
        elif verb == "linked":
            party = self.parties.get(pid)
            if party:
                if p["relation"] == "member_of":
                    party.memberships.append(p["target"])
                elif p["relation"] == "employed_by":
                    party.employers.append(p["target"])
                party.history.append(e["id"])

    def _apply_employer(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        eid = p["entity_id"]
        if verb == "declared":
            self.employers[eid] = Employer(id=eid, name=p["name"], industry=p.get("industry"),
                                            asserted_by=e["actor"], provenance=[e["id"]],
                                            history=[e["id"]])
        elif verb == "closed":
            employer = self.employers.get(eid)
            if employer:
                employer.status = p.get("status", "defunct")
                employer.history.append(e["id"])

    def _apply_mission(self, e: dict) -> None:
        verb = grammar.verb(e["kind"])
        p = e["payload"]
        mid = p["entity_id"]
        if verb == "declared":
            tr = p.get("target_range")
            self.missions[mid] = Mission(
                id=mid, name=p["name"], target_metric=p.get("target_metric", ""),
                target_value=p.get("target_value"),
                target_range=tuple(tr) if tr else None,
                target_date=p.get("target_date"), tolerance=p.get("tolerance"),
                asserted_by=e["actor"], provenance=[e["id"]], history=[e["id"]],
            )
        elif verb == "closed":
            mission = self.missions.get(mid)
            if mission:
                mission.status = p.get("status", "closed")
                mission.history.append(e["id"])
        elif verb == "updated":
            mission = self.missions.get(mid)
            if mission:
                for k, v in p.items():
                    if k in ("target_metric", "target_value", "target_date", "tolerance"):
                        setattr(mission, k, v)
                    elif k == "target_range" and v is not None:
                        mission.target_range = tuple(v)
                mission.history.append(e["id"])
