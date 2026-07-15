"""
Kernel — the minimal syscall surface.

Seven operations. Everything else in the system is either storage
(eventlog, canon) or a peripheral (models).

    ingest(text, source)          -> event
    derive(event_id)              -> [claims]      (uses current model)
    retrieve(query)               -> {events, claims, provenance}
    ask(question)                 -> answer + citations
    update_claim(id, ...)         -> event
    link(a, relation, b)          -> event
    resolve_conflict(a, b, keep)  -> event

Note what the kernel does NOT contain: any model-specific logic, any
prompt strings, any state of its own. The model is a constructor
argument, replaceable at any moment. All state lives in the event log;
the Canon is rebuilt from it.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from .canon import Canon, Claim
from .errors import EventNotFoundError
from .eventlog import EventLog
from .models import ModelAdapter

log = logging.getLogger("foundry.kernel")


class Kernel:
    def __init__(self, log: EventLog, model: ModelAdapter):
        self.log = log
        self.model = model
        self.canon = Canon(log)

    # -------------------------------------------------------------- model swap

    def swap_model(self, model: ModelAdapter) -> None:
        """The entire cost of changing CPUs. State is untouched."""
        self.model = model

    # ------------------------------------------------------------------ ingest

    def ingest(self, text: str, source: str = "manual") -> dict:
        """Preserve original material forever. Nothing is interpreted yet."""
        return self.log.append("ingest", {"text": text, "source": source})

    # ------------------------------------------------------------------ derive

    def derive(self, event_id: str) -> list[Claim]:
        """
        Ask the *current* model to extract claims from a stored event.
        Each claim becomes a `claim.derived` event whose actor is the
        model's name — provenance includes who did the extracting.
        """
        src = self.log.get(event_id)
        if not src or src["kind"] != "ingest":
            raise EventNotFoundError(f"no ingest event {event_id!r}")
        raw_claims = self.model.extract_claims(src["payload"]["text"])
        log.info("%s extracted %d claims from event %s",
                 self.model.name, len(raw_claims), event_id[:8])
        out = []
        for rc in raw_claims:
            cid = str(uuid.uuid4())
            e = self.log.append(
                "claim.derived",
                {
                    "claim_id": cid,
                    "statement": rc.statement,
                    "confidence": rc.confidence,
                    "evidence": [rc.evidence],
                    "provenance": [event_id],
                },
                actor=self.model.name,
            )
            self.canon.apply(e)
            out.append(cid)
        return [self.canon.get(c) for c in out]

    # ---------------------------------------------------------------- retrieve

    def retrieve(self, query: str, k: int = 5) -> dict[str, Any]:
        """
        Returns events, claims AND provenance — never bare text chunks.
        Scoring is deliberately dumb (word overlap); retrieval quality is
        not the thesis under test, replaceability is.
        """
        qwords = _words(query)

        def score(text: str) -> int:
            return len(qwords & _words(text))

        events = sorted(
            (e for e in self.log.events() if e["kind"] == "ingest"),
            key=lambda e: score(e["payload"]["text"]), reverse=True,
        )
        claims = sorted(self.canon.active(),
                        key=lambda c: score(c.statement), reverse=True)
        top_claims = [c for c in claims[:k] if score(c.statement) > 0]
        return {
            "events": [e for e in events[:k] if score(e["payload"]["text"]) > 0],
            "claims": top_claims,
            "provenance": {c.id: self.canon.explain(c.id) for c in top_claims},
        }

    # --------------------------------------------------------------------- ask

    def ask(self, question: str) -> dict[str, Any]:
        """Answer from retrieved claims, with citations back to source events."""
        r = self.retrieve(question)
        context = "\n".join(
            f"- {c.statement} (confidence {c.confidence}, claim {c.id[:8]})"
            for c in r["claims"]
        )
        answer = self.model.answer(question, context)
        return {
            "answer": answer,
            "model": self.model.name,
            "citations": [
                {
                    "claim": c.statement,
                    "claim_id": c.id,
                    "derived_by": c.derived_by,
                    "source_events": c.provenance,
                    "evidence": c.evidence,
                }
                for c in r["claims"]
            ],
        }

    # ------------------------------------------------------------ claim admin

    def update_claim(self, claim_id: str, statement: str | None = None,
                     confidence: float | None = None, reason: str = "",
                     actor: str = "user") -> dict:
        payload = {"claim_id": claim_id, "reason": reason}
        if statement is not None:
            payload["statement"] = statement
        if confidence is not None:
            payload["confidence"] = confidence
        e = self.log.append("claim.updated", payload, actor=actor)
        self.canon.apply(e)
        return e

    def link(self, claim_id: str, relation: str, target_id: str,
             actor: str = "user") -> dict:
        e = self.log.append(
            "claim.linked",
            {"claim_id": claim_id, "relation": relation, "target": target_id},
            actor=actor,
        )
        self.canon.apply(e)
        return e

    def resolve_conflict(self, loser_id: str, winner_id: str,
                         reason: str = "", actor: str = "user") -> dict:
        """Supersede one claim in favour of another. Nothing is deleted."""
        e = self.log.append(
            "claim.superseded",
            {"claim_id": loser_id, "superseded_by": winner_id, "reason": reason},
            actor=actor,
        )
        self.canon.apply(e)
        return e

    # ------------------------------------------------------------- bookkeeping

    def underived(self, by_model: str | None = None) -> list[dict]:
        """
        Ingest events not yet derived (optionally: not yet derived by a
        specific model). No separate bookkeeping store exists or is
        needed — derivation state is itself derivable from the log,
        since every claim.derived event carries provenance and actor.
        """
        derived_from: set[tuple[str, str]] = set()
        for e in self.log.events():
            if e["kind"] == "claim.derived":
                for src in e["payload"].get("provenance", []):
                    derived_from.add((src, e["actor"]))
        out = []
        for e in self.log.events():
            if e["kind"] != "ingest":
                continue
            if by_model:
                done = (e["id"], by_model) in derived_from
            else:
                done = any(src == e["id"] for src, _ in derived_from)
            if not done:
                out.append(e)
        return out

    # ----------------------------------------------------------------- explain

    def why(self, claim_id: str) -> dict | None:
        """'Why do you believe this?' — the provenance contract."""
        return self.canon.explain(claim_id)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 3}
