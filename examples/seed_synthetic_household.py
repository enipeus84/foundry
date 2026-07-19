"""
CLI wrapper around `foundry.demo_data.build` — seeds an event log with
the synthetic Morgan household (RFC-003.2): ~24 months of realistic
history, all five Mission Control KPIs populated, a full Mission ->
Decision -> Execution -> Outcome -> Review -> Learning lifecycle.

*** THIS IS SYNTHETIC DATA. Not a real household. Not an import
*** feature. Not an onboarding workflow.

The actual dataset construction lives in `foundry.demo_data` (not
here) so `foundry.web`'s optional demo-mode startup hook
(RFC-003.3, `FOUNDRY_DEMO_DATA=true`) can reuse the identical builder
without importing from this unpackaged `examples/` directory.

Run from the repo root:

    python3 examples/seed_synthetic_household.py
    uvicorn foundry.web:app --port 8000

Refuses to run against a non-empty event log (the same guard
examples/seed_mission_control.py uses) so it can never silently
double-seed or corrupt an existing dataset.
"""

from __future__ import annotations

import os

from foundry.core.entities import EntityProjection
from foundry.demo_data import build
from foundry.eventlog import EventLog


def main() -> None:
    path = os.environ.get("FOUNDRY_DATA_PATH", "foundry_data/events.jsonl")
    log = EventLog(path)
    if any(True for _ in log.events()):
        raise SystemExit(f"{path} already has events — refusing to double-seed.")

    household = build(log)
    mission = next(iter(EntityProjection(log).missions.values()))

    n_events = sum(1 for _ in log.events())
    print(f"seeded {n_events} events -> {path}")
    print(f"household {household.household_id[:8]}, mission {mission.id[:8]} ({mission.name})")
    print(f"members: alex={household.alex_id[:8]} sam={household.sam_id[:8]} "
          f"emily={household.emily_id[:8]} oliver={household.oliver_id[:8]}")


if __name__ == "__main__":
    main()
