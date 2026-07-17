"""
Foundry Core — the domain-agnostic layer every product domain depends
on (docs/specifications/000-core-domain-model.md).

RFC-001 implements this package and nothing else: no Finance, no
Flight Deck UI, no other domain. Finance (001) will *consume* this
package rather than duplicate it.

Core adds no write path the substrate doesn't already have. Every
mutation here is `EventLog.append` under a `core.` (or unprefixed
`claim.*`) event kind; every piece of state here is a projection —
deletable, rebuildable, and never authoritative on its own.

    from foundry.core import Party, Employer, Mission, EntityProjection
    from foundry.core import Decision, DecisionOutcome, DecisionProjection
    from foundry.core.metrics import MetricRequest, MetricResult, MetricRegistry
    from foundry.core.evidence import EvidenceIndex
    from foundry.core.flight_deck import compose_flight_deck

Submodules:
    grammar.py            the shared five-verb event grammar (000 §6)
    vocab.py               controlled vocabularies (000 §7)
    scope.py               subjects & drill-down resolution (000 §10)
    entities.py             Party, Employer, Mission (000 §8)
    evidence.py             Claim tagging + the Core Evidence Index (000 §11)
    decisions.py             Decision lifecycle (000 §12)
    metrics.py               MetricRequest/Result, Metric Registry (000 §13)
    mission_evaluation.py    domain calculates / Core evaluates / AI explains
    flight_deck.py           Flight Deck composition (000 §14)
"""

from .entities import Employer, EntityProjection, Mission, Party
from .decisions import Decision, DecisionOutcome, DecisionProjection
from .evidence import EvidenceIndex
from .metrics import MetricProvider, MetricRegistry, MetricRequest, MetricResult
from .scope import Subject
from .flight_deck import Tile, compose_flight_deck, compose_tile
from .mission_evaluation import evaluate_mission_status, get_mission_status

__all__ = [
    "Party", "Employer", "Mission", "EntityProjection",
    "Decision", "DecisionOutcome", "DecisionProjection",
    "EvidenceIndex",
    "MetricProvider", "MetricRegistry", "MetricRequest", "MetricResult",
    "Subject",
    "Tile", "compose_flight_deck", "compose_tile",
    "evaluate_mission_status", "get_mission_status",
]
