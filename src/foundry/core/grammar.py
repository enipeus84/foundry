"""
Shared event grammar — 000-core-domain-model.md §6.

Five verbs (`declared`, `updated`, `closed`, `linked`, `tagged`) that
every product domain, including Core itself, uses to mutate an entity.
These are thin wrappers over `EventLog.append`: Core adds no write path
the substrate doesn't already have (constitutional invariant 1/2).

`declared`/`updated`/`closed`/`linked` are generic over any
`<prefix>.<type>` entity (Party, Employer, Mission, Decision, Decision
Outcome here; Account, Transaction, etc. in a future Finance package).
`tagged` has no generic helper here: V1's only concrete use of it is on
`Claim` (unprefixed `claim.tagged`), which lives in `evidence.py`
alongside the vocabulary it's validated against.
"""

from __future__ import annotations

import uuid
from typing import Any

from foundry.eventlog import EventLog

from . import vocab
from ..errors import VocabularyError


def declare(log: EventLog, prefix: str, type_: str, entity_id: str,
            attributes: dict[str, Any], actor: str = "user") -> dict:
    """`<prefix>.<type>.declared` — a new entity is asserted to exist."""
    payload = {"entity_id": entity_id, **attributes}
    return log.append(f"{prefix}.{type_}.declared", payload, actor=actor)


def update(log: EventLog, prefix: str, type_: str, entity_id: str,
           changes: dict[str, Any], reason: str, actor: str = "user") -> dict:
    """`<prefix>.<type>.updated` — an attribute is revised, with a
    reason. History is appended by the reading projection; nothing is
    overwritten in the log."""
    payload = {"entity_id": entity_id, "reason": reason, **changes}
    return log.append(f"{prefix}.{type_}.updated", payload, actor=actor)


def close(log: EventLog, prefix: str, type_: str, entity_id: str, reason: str,
          actor: str = "user", status: str | None = None,
          status_vocabulary: vocab.ExtensibleVocabulary | None = None,
          **extra: Any) -> dict:
    """`<prefix>.<type>.closed` — a terminal lifecycle state. Not used
    for corrections. `status` lets a caller record *which* terminal
    state was reached (e.g. Mission's `achieved` vs `abandoned`) without
    a second verb; when `status_vocabulary` is given, `status` is
    validated against it before the write — the same "never let an
    ungoverned value reach the append-only log" discipline `relate()`
    already applies to relations. Validation is opt-in here (unlike
    `relate()`, where it's mandatory) because not every entity's
    terminal-state label is one of `000` §7's controlled vocabularies;
    callers that do have one (Mission's `mission_status`) must pass it."""
    if status is not None and status_vocabulary is not None and status not in status_vocabulary:
        raise VocabularyError(
            f"{status!r} is not a valid {status_vocabulary.name} value "
            f"(known: {sorted(status_vocabulary.values)})")
    payload = {"entity_id": entity_id, "reason": reason, **extra}
    if status is not None:
        payload["status"] = status
    return log.append(f"{prefix}.{type_}.closed", payload, actor=actor)


def relate(log: EventLog, prefix: str, type_: str, entity_id: str,
           relation: str, target: str, vocabulary: vocab.ExtensibleVocabulary,
           actor: str = "user") -> dict:
    """`<prefix>.<type>.linked` — a relationship to another addressable
    entity. `relation` must be a member of the given controlled
    vocabulary (design principle 2: never a bare string), checked
    *before* the append — an invalid relation must never reach the
    append-only log, because it can never be un-written afterwards."""
    if relation not in vocabulary:
        raise VocabularyError(
            f"{relation!r} is not a valid {vocabulary.name} value "
            f"(known: {sorted(vocabulary.values)})")
    payload = {"entity_id": entity_id, "relation": relation, "target": target}
    return log.append(f"{prefix}.{type_}.linked", payload, actor=actor)


def new_id() -> str:
    return str(uuid.uuid4())
