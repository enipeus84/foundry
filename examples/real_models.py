"""
Cross-vendor swap with real models. Requires:

    pip install ".[models]"
    export ANTHROPIC_API_KEY=...
    export OPENAI_API_KEY=...
    python3 examples/real_models.py
"""

import os

from foundry import EventLog, Kernel
from foundry.models import AnthropicAdapter, OpenAIAdapter

k = Kernel(
    EventLog("real_data/events.jsonl"),
    AnthropicAdapter(os.environ["ANTHROPIC_API_KEY"]),
)

e = k.ingest(
    "The Foundry substrate is an append-only event log. "
    "Claims derived from events carry provenance and model identity.",
    source="example",
)
claims = k.derive(e["id"])                       # Anthropic derives
print(f"{len(claims)} claims derived by {k.model.name}")

k.swap_model(OpenAIAdapter(os.environ["OPENAI_API_KEY"]))
r = k.ask("What carries provenance?")            # OpenAI answers over them
print(f"\n{r['model']} answering over {r['citations'][0]['derived_by']} claims:")
print(r["answer"])
