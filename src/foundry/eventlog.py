"""
Event Log — the ground truth layer.

An append-only JSONL file. Every fact the system will ever know enters
here first and is never modified afterwards.

Design decisions:
- JSONL, not a database. One event per line. Human-readable, greppable,
  diffable, trivially durable, trivially replaceable.
- Hash chaining. Each event records the SHA-256 of the previous event,
  so tampering (or accidental editing) is detectable. This is the
  cheapest possible integrity guarantee — not cryptographic security,
  just an honesty check.
- Events carry a `kind`. Crucially, *claim mutations are also events*
  (kind = "claim.derived", "claim.updated", "claim.superseded", ...).
  The Canon is therefore a pure projection of this log and can be
  deleted and rebuilt at any time. Nothing outside this file is
  load-bearing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Iterator

log = logging.getLogger("foundry.eventlog")

GENESIS_HASH = "0" * 64


def _canonical(obj: dict) -> str:
    """Deterministic JSON serialisation, so hashes are stable."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class EventLog:
    """Append-only log. The only write operation is `append`."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        # Cache of the last event's hash so append is O(1), not a file
        # scan. Assumes single-writer access to the log file; concurrent
        # writers are out of scope for V1.0 (see docs/roadmap.md).
        self._last = self._scan_last_hash()

    # ------------------------------------------------------------------ write

    def append(self, kind: str, payload: dict, actor: str = "user") -> dict:
        """
        Append one event. Returns the stored event (with id, hash, prev_hash).

        `actor` records *who or what* produced the event — a human, or a
        named model. This matters: when a model derives a claim, the model's
        identity is part of the provenance, not an invisible substrate.
        """
        prev = self._last
        event = {
            "id": str(uuid.uuid4()),
            "ts": time.time(),
            "kind": kind,
            "actor": actor,
            "payload": payload,
            "prev_hash": prev,
        }
        event["hash"] = hashlib.sha256(
            (_canonical({k: v for k, v in event.items() if k != "hash"})).encode()
        ).hexdigest()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(_canonical(event) + "\n")
        self._last = event["hash"]
        log.debug("appended %s event %s", kind, event["id"])
        return event

    # ------------------------------------------------------------------- read

    def events(self) -> Iterator[dict]:
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def get(self, event_id: str) -> dict | None:
        for e in self.events():
            if e["id"] == event_id:
                return e
        return None

    def verify(self) -> bool:
        """
        Recompute the hash chain. False means the log has been altered.

        Known limitation (documented, deliberate): the chain detects
        edits and insertions but NOT truncation of trailing events —
        a shortened log is still internally consistent. Detecting
        truncation requires anchoring the head hash somewhere external
        (see docs/roadmap.md, "Integrity anchoring").
        """
        prev = GENESIS_HASH
        for e in self.events():
            if e["prev_hash"] != prev:
                return False
            body = {k: v for k, v in e.items() if k != "hash"}
            if hashlib.sha256(_canonical(body).encode()).hexdigest() != e["hash"]:
                return False
            prev = e["hash"]
        return True

    # ---------------------------------------------------------------- private

    def _scan_last_hash(self) -> str:
        last = GENESIS_HASH
        for e in self.events():
            last = e["hash"]
        return last
