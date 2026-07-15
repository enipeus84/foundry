"""
Acceptance Demonstration — the 8-step workflow from the brief, end to end.
Run:  python3 demo.py
"""

import shutil
from pathlib import Path

from foundry.eventlog import EventLog
from foundry.kernel import Kernel
from foundry.models import MockModelAlpha, MockModelBeta

DATA = Path("demo_data")
shutil.rmtree(DATA, ignore_errors=True)

CONVERSATION = """\
Sarah: The client meeting is confirmed for Thursday.
James: Good. Their budget is 75000 pounds for phase one.
Sarah: Alice is the technical lead on their side.
James: Does she prefer weekly or fortnightly reviews?
Sarah: Weekly. And the deadline is 15 September.
"""


def step(n, title):
    print(f"\n{'='*62}\nSTEP {n}: {title}\n{'='*62}")


k = Kernel(EventLog(DATA / "events.jsonl"), MockModelAlpha())

step(1, "Import a conversation")
e = k.ingest(CONVERSATION, source="slack-export")
print(f"ingested as event {e['id'][:8]}")

step(2, "Events are stored (immutably, hash-chained)")
print(f"events in log: {sum(1 for _ in k.log.events())}")
print(f"chain integrity: {'OK' if k.log.verify() else 'FAIL'}")

step(3, "Claims are extracted (by mock-alpha)")
claims = k.derive(e["id"])
for c in claims:
    print(f"  {c.id[:8]}  ({c.confidence})  {c.statement}")

step(4, "Relationships are built")
budget = next(c for c in claims if "75000" in c.statement)
deadline = next(c for c in claims if "September" in c.statement)
k.link(budget.id, "constrains", deadline.id)
print(f"linked: '{budget.statement}' --constrains--> '{deadline.statement}'")

step(5, "Ask questions")
q = "What is the client budget?"
print(f"Q: {q}")
r = k.ask(q)
print(f"A: {r['answer']}")

step(6, "Answers carry provenance")
top = r["citations"][0]
print(f"claim:        {top['claim']}")
print(f"derived by:   {top['derived_by']}")
print(f"evidence:     {top['evidence']}")
print(f"source event: {top['source_events'][0][:8]} (original text preserved)")

step(7, "Switch LLM (one line, zero state migration)")
k.swap_model(MockModelBeta())
print(f"model is now: {k.model.name}")

step(8, "Continue seamlessly on the same substrate")
r2 = k.ask("Who is the technical lead?")
print(f"A: {r2['answer']}")
print("citation provenance still points at claims derived by the OLD model:")
for c in r2["citations"][:1]:
    print(f"  claim by {c['derived_by']}, answered by {r2['model']}")

e2 = k.ingest("Alice was promoted to programme director.")
new = k.derive(e2["id"])
k.resolve_conflict(
    next(c for c in claims if "technical lead" in c.statement).id,
    new[0].id,
    reason="role changed; newer source",
)
print("\nnew model derived a conflicting claim; old claim superseded, not deleted:")
old = next(c for c in k.canon.claims.values() if c.status == "superseded")
print(f"  superseded: '{old.statement}' -> superseded_by {old.superseded_by[:8]}")
print(f"  still explainable: {k.why(old.id) is not None}")

print(f"\nfinal integrity check: {'OK' if k.log.verify() else 'FAIL'}")
print("actors in canon:", {c.derived_by for c in k.canon.claims.values()})
print("\nAll 8 steps demonstrated on a single immutable event log.")
