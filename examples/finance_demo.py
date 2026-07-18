"""
RFC-002 Finance Domain, end to end: build the synthetic Parker-Brads
household, register the five Finance metrics, and show the Flight Deck
(foundry.core.flight_deck) receiving real values through the Metric
Registry — the same dispatch path a second, unrelated domain would use
alongside it, with no import edge in either direction. Run from the
repo root:

    python3 examples/finance_demo.py
"""

from foundry.core.entities import EntityProjection, declare_mission
from foundry.core.evidence import EvidenceIndex
from foundry.core.flight_deck import compose_flight_deck
from foundry.core.metrics import MetricRegistry, MetricRequest
from foundry.core.scope import Subject
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.fixtures import build_parker_brads_household
from foundry.finance.metrics import FinanceMetricProvider

log = EventLog("finance_demo_data/events.jsonl")

# 1. Build the household: Core Party/Employer state, plus Finance's own
#    accounts, assets, obligations, positions, and six months of
#    categorised transactions.
household = build_parker_brads_household(log)
print(f"Household: {household.household_id[:8]}  "
      f"(Chris {household.chris_id[:8]}, Fiona {household.fiona_id[:8]}, "
      f"Hamish {household.hamish_id[:8]}, Harriet {household.harriet_id[:8]})")

# 2. A Mission the Flight Deck will evaluate against a real Finance
#    metric (000 §8's three-step split: Finance calculates, Core
#    evaluates, no AI in this path at all).
mission = declare_mission(
    log, "Grow household net worth", target_metric="finance.net_worth",
    target_value=400_000.0, tolerance=50_000.0,
)

# 3. Wire Finance into Core purely through the Metric Registry — this
#    is the only place either package's code meets the other's.
core_entities = EntityProjection(log)
finance_entities = FinanceEntityProjection(log)
evidence_index = EvidenceIndex(log)
registry = MetricRegistry()
registry.register(FinanceMetricProvider(finance_entities, core_entities))

# 4. Compose the Flight Deck's Finance-sourced KPIs (001 §23):
household_scope = Subject("party", household.household_id)
tiles = compose_flight_deck(
    [
        ("finance.net_worth", household_scope, mission.id),
        ("finance.liquidity_runway", household_scope, None),
    ],
    registry, core_entities, evidence_index, household.as_of,
)

print("\nFlight Deck tiles (real metrics, dispatched through the Metric Registry):")
for tile in tiles:
    result = tile.current_value
    print(f"  {tile.metric_id:<28} status={result.status:<11} "
          f"value={result.value!r:<10} unit={result.unit_or_currency}  "
          f"rag={tile.rag_status}  inputs={len(result.input_references)} events")

print("\nIndividual attribution (must sum to the household total, 001 §9):")
household_net_worth = registry.dispatch(MetricRequest(
    metric_id="finance.net_worth", scope=household_scope, as_of=household.as_of)).value
attributed_total = 0.0
for label, person_id in (("Chris", household.chris_id), ("Fiona", household.fiona_id),
                          ("Hamish", household.hamish_id), ("Harriet", household.harriet_id)):
    result = registry.dispatch(MetricRequest(
        metric_id="finance.net_worth", scope=Subject("party", person_id), as_of=household.as_of))
    print(f"  {label:<8} status={result.status:<11} value={result.value!r}")
    if result.status == "available":
        attributed_total += result.value
print(f"  {'sum':<8} {attributed_total:.2f}  vs household total {household_net_worth:.2f}")

print("\nEmployer concentration (Chris's stake in his own employer's stock, 001 §21):")
concentration = registry.dispatch(MetricRequest(
    metric_id="finance.employer_concentration", scope=Subject("party", household.chris_id),
    as_of=household.as_of))
print(f"  status={concentration.status}  value={concentration.value:.2%}")
