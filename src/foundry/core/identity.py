"""Canonical, temporal facts about Person identity.

Date of birth is intentionally a typed Core fact rather than a convenient
Party attribute.  It is calendar data: timestamps, time zones and persisted
ages have no place in this contract.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from foundry.eventlog import EventLog


EVENT_KIND = "core.person.date_of_birth.declared"
MAX_HUMAN_AGE = 130


class PersonIdentityError(ValueError):
    """A proposed canonical person-identity fact is inadmissible."""


def parse_date_of_birth(value: str | date) -> date:
    """Validate an ISO calendar date against the bounded human-age contract."""
    if isinstance(value, datetime):
        raise PersonIdentityError("date_of_birth must be a calendar date")
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise PersonIdentityError("date_of_birth must be YYYY-MM-DD") from exc
    elif isinstance(value, date):
        parsed = value
    else:
        raise PersonIdentityError("date_of_birth must be YYYY-MM-DD")
    today = date.today()
    if parsed > today:
        raise PersonIdentityError("date_of_birth cannot be future-dated")
    try:
        earliest = today.replace(year=today.year - MAX_HUMAN_AGE)
    except ValueError:  # 29 February in a non-leap boundary year.
        earliest = date(today.year - MAX_HUMAN_AGE, 3, 1)
    if parsed < earliest:
        raise PersonIdentityError("date_of_birth exceeds the human-age limit")
    return parsed


def age_years(date_of_birth: date, as_of: float) -> int:
    """Return completed whole years at ``as_of``; 29 February becomes 1 March."""
    assessed = datetime.fromtimestamp(as_of, timezone.utc).date()
    try:
        birthday = date_of_birth.replace(year=assessed.year)
    except ValueError:
        birthday = date(assessed.year, 3, 1)
    return assessed.year - date_of_birth.year - (assessed < birthday)


def declare_person_date_of_birth(
    log: EventLog,
    person_id: str,
    date_of_birth: str | date,
    *,
    actor: str = "user",
) -> dict:
    """Append a typed DOB declaration, superseding any prior declaration."""
    if not isinstance(person_id, str) or not person_id.strip():
        raise PersonIdentityError("person_id is required")
    # Import here to keep entities as the Core projection owner.
    from .entities import EntityProjection

    entities = EntityProjection(log)
    person = entities.parties.get(person_id)
    if person is None or person.party_type != "person" or person.status != "active":
        raise PersonIdentityError("date_of_birth requires an active Person")
    parsed = parse_date_of_birth(date_of_birth)
    payload = {"person_id": person_id, "date_of_birth": parsed.isoformat()}
    if person.date_of_birth_provenance:
        payload["supersedes"] = person.date_of_birth_provenance[-1]
    return log.append(EVENT_KIND, payload, actor=actor)
