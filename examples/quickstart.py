"""
Copy-paste quickstart: ingest, derive, ask, explain, swap.
Run from the repo root after `pip install -e .`:

    python3 examples/quickstart.py
"""

from foundry import EventLog, Kernel
from foundry.models import MockModelAlpha, MockModelBeta

k = Kernel(EventLog("quickstart_data/events.jsonl"), MockModelAlpha())

# 1. Preserve source material forever
e = k.ingest(
    "Sarah: The client meeting is confirmed for Thursday.\n"
    "James: Their budget is 75000 pounds for phase one.\n"
    "Sarah: Alice is the technical lead on their side.",
    source="slack-export",
)

# 2. Extract attributed claims
for c in k.derive(e["id"]):
    print(f"claim [{c.derived_by}] ({c.confidence}): {c.statement}")

# 3. Ask, with citations back to source events
r = k.ask("What is the budget?")
print("\nanswer:", r["answer"])
for cite in r["citations"][:1]:
    print("cited claim:", cite["claim"])
    print("source event:", cite["source_events"][0])

# 4. 'Why do you believe this?' — full provenance
first = k.canon.active()[0]
why = k.why(first.id)
print("\nwhy:", why["claim"], "| derived by", why["derived_by"])

# 5. Swap models. State untouched; provenance intact.
k.swap_model(MockModelBeta())
print("\nafter swap:", k.ask("Who is the technical lead?")["answer"])
