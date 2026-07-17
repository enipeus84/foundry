"""
Flight Deck output contract — 000-core-domain-model.md §14.

A Core composition surface: it dispatches `MetricRequest`s through the
`MetricRegistry` and reads the `EvidenceIndex` and `EntityProjection`;
it never imports or calls a domain's calculation code directly. This
is what makes composing a page from two unrelated domains possible
without either domain's module appearing in the other's import graph —
demonstrated in tests with two independent mock providers, standing in
for Finance and a hypothetical second domain (RFC-001 implements no
real domain).

The Flight Deck is a **consumer**, never a producer: nothing in this
module appends an event. `compose_tile`/`compose_flight_deck` are pure
reads over already-built projections and an already-populated registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .entities import EntityProjection
from .evidence import EvidenceIndex
from .metrics import MetricRegistry, MetricRequest, MetricResult
from .mission_evaluation import evaluate_mission_status
from .scope import Subject, resolve_scope


@dataclass
class Tile:
    metric_id: str
    scope: Subject
    current_value: MetricResult
    trajectory: str | None
    variance_from_target: float | None
    rag_status: str | None
    confidence_or_freshness: object
    strategic_vulnerability: list[str] = field(default_factory=list)
    next_decision: list[str] = field(default_factory=list)
    drill_down_target: str | None = None
    calculation_and_evidence_references: dict = field(default_factory=dict)


def compose_tile(metric_id: str, scope: Subject, registry: MetricRegistry,
                  entities: EntityProjection, evidence_index: EvidenceIndex,
                  as_of: float, mission_id: str | None = None,
                  domain_resource_ids: frozenset[str] = frozenset()) -> Tile:
    """Compose one tile: dispatch the metric request, evaluate Mission
    status against it if a Mission is linked, and pull strategic
    vulnerabilities / next-decision candidates from the shared Evidence
    Index for every subject the requested scope resolves to.

    `mission_id` (not a `Mission` object) is looked up fresh from
    `entities` on every call — the same reasoning as
    `mission_evaluation.get_mission_status`: a `Mission` snapshot held
    by the caller could be stale relative to the `entities` projection
    also being passed in, and this is the one place that risk is
    structurally eliminated rather than left to caller discipline."""
    result = registry.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))

    rag_status = None
    variance = None
    mission = entities.missions.get(mission_id) if mission_id else None
    if mission is not None:
        rag_status = evaluate_mission_status(mission, result)
        if result.value is not None and mission.target_value is not None:
            variance = result.value - mission.target_value

    vulnerabilities: set[str] = set()
    recommendations: set[str] = set()
    for subject in resolve_scope(scope, entities, domain_resource_ids):
        for claim_id in evidence_index.claims_concerning(subject.id):
            insight_type = evidence_index.current_tag(claim_id, "insight_type")
            if insight_type == "vulnerability":
                vulnerabilities.add(claim_id)
            elif insight_type == "recommendation":
                recommendations.add(claim_id)

    return Tile(
        metric_id=metric_id, scope=scope, current_value=result,
        trajectory=result.projection_series_reference,
        variance_from_target=variance, rag_status=rag_status,
        confidence_or_freshness=result.confidence_or_quality,
        strategic_vulnerability=sorted(vulnerabilities),
        next_decision=sorted(recommendations),
        drill_down_target=result.drill_down_target,
        calculation_and_evidence_references={
            "input_references": result.input_references,
            "evidence_references": result.evidence_references,
            "assumption_references": result.assumption_references,
        },
    )


def compose_flight_deck(tile_specs, registry: MetricRegistry, entities: EntityProjection,
                         evidence_index: EvidenceIndex, as_of: float) -> list[Tile]:
    """`tile_specs`: an iterable of `(metric_id, scope, mission_id_or_None)`.
    Composes whatever is asked for; the 5-7 top-page indicator cap
    (000 §14) is a product decision this function does not enforce —
    it only guarantees any such set is composable without importing
    domain calculation code."""
    return [
        compose_tile(metric_id, scope, registry, entities, evidence_index, as_of, mission_id)
        for metric_id, scope, mission_id in tile_specs
    ]
