"""
Ingest real conversation exports.

    python3 examples/ingest_exports.py path/to/conversations.json
"""

import sys

from foundry import EventLog, Kernel
from foundry.ingestors import ingest_chatgpt_export, ingest_claude_export
from foundry.models import MockModelAlpha

k = Kernel(EventLog("export_data/events.jsonl"), MockModelAlpha())
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
fn = ingest_chatgpt_export if '"mapping"' in text else ingest_claude_export
events = fn(k, path)
print(f"ingested {len(events)} conversations")
for e in events:
    claims = k.derive(e["id"])
    print(f"  {e['payload']['source']}: {len(claims)} claims")
print("underived remaining:", len(k.underived()))
