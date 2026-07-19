"""
Seed an event log for Mission Control (RFC-003). Run from the repo
root, then start the server:

    python3 examples/seed_mission_control.py          # writes FOUNDRY_DATA_PATH
    uvicorn foundry.web:app --port 8000

Writes the synthetic Parker-Brads household (the same fixture the test
suite validates), an active Mission for the console to steer by, and
one recommendation Claim for the NEXT DECISION slot — every value the
console then shows is computed by Finance from these replayed events,
through the Metric Registry. Mission Control itself never writes;
seeding is this script's job precisely so the surface stays read-only.
"""

from __future__ import annotations

import os

from foundry.core.entities import declare_mission
from foundry.core.evidence import concern, derive_claim_directly, tag_claim
from foundry.eventlog import EventLog
from foundry.finance.fixtures import build_parker_brads_household

path = os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")
log = EventLog(path)
if any(True for _ in log.events()):
    raise SystemExit(f"{path} already has events — refusing to double-seed.")

household = build_parker_brads_household(log)

mission = declare_mission(
    log, "Financial independence glide path",
    target_metric="finance.net_worth",
    target_value=450_000.0, tolerance=50_000.0,
)

_, claim_id = derive_claim_directly(
    log,
    statement="Reduce employer concentration below 25% before the next vesting date.",
    confidence=0.8,
    evidence=["Anchor Systems stock is 32% of the investable portfolio."],
    provenance=[household.chris_id],
    actor="user",
)
tag_claim(log, claim_id, "insight_type", "recommendation")
concern(log, claim_id, household.household_id)

print(f"seeded {sum(1 for _ in log.events())} events -> {path}")
print(f"household {household.household_id[:8]}, mission {mission.id[:8]} ({mission.name})")
