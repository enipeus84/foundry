"""
Minimal CLI. Just enough to drive the kernel by hand.

    python -m foundry.cli ingest "some text"
    python -m foundry.cli derive <event_id>
    python -m foundry.cli claims
    python -m foundry.cli ask "question"
    python -m foundry.cli why <claim_id>
    python -m foundry.cli swap alpha|beta
    python -m foundry.cli verify
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .eventlog import EventLog
from .kernel import Kernel
from .models import MockModelAlpha, MockModelBeta

# Data location is configurable so the CLI is portable and testable.
# Default keeps state in the working directory — visible, greppable.
import os
DATA_DIR = Path(os.environ.get("FOUNDRY_DATA", "foundry_data"))
STATE = DATA_DIR / "events.jsonl"
MODEL_FILE = DATA_DIR / "current_model"   # persisted model selection

MODELS = {"alpha": MockModelAlpha, "beta": MockModelBeta}


def _kernel() -> Kernel:
    name = MODEL_FILE.read_text().strip() if MODEL_FILE.exists() else "alpha"
    return Kernel(EventLog(STATE), MODELS[name]())


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd, *args = argv
    k = _kernel()

    if cmd == "ingest":
        e = k.ingest(" ".join(args))
        print(f"stored event {e['id']}")
    elif cmd == "derive":
        for c in k.derive(args[0]):
            print(f"{c.id[:8]}  ({c.confidence})  {c.statement}")
    elif cmd == "claims":
        for c in k.canon.active():
            print(f"{c.id[:8]}  [{c.derived_by}]  {c.statement}")
    elif cmd == "ask":
        r = k.ask(" ".join(args))
        print(r["answer"])
        for c in r["citations"]:
            print(f"  ↳ {c['claim']}  (claim {c['claim_id'][:8]}, "
                  f"by {c['derived_by']}, events {[e[:8] for e in c['source_events']]})")
    elif cmd == "why":
        print(json.dumps(k.why(args[0]), indent=2, default=str))
    elif cmd == "swap":
        MODEL_FILE.parent.mkdir(exist_ok=True)
        MODEL_FILE.write_text(args[0])
        print(f"model is now {args[0]} — state untouched")
    elif cmd == "verify":
        print("log integrity:", "OK" if k.log.verify() else "TAMPERED")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
