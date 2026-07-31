"""Pure Mission Console Model (RFC-010).

The model owns ordering, grouping, visibility, disclosure placement and card
priority.  It performs no I/O, reads no clock and emits no markup.  Renderers
must consume the supplied order verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

from .mission_assessment import (
    DeltaV,
    MissionAssessment,
    MissionConfidence,
    MissionDefinition,
    MissionMargin,
    MissionMilestone,
    MissionTrajectoryView,
    RecommendationAssessment,
    TelemetryItem,
)
from .metrics import MetricResult


REGION_ORDER = (
    "mission-hero",
    "flight-analysis",
    "essential-telemetry",
    "next-burn",
    "progressive-disclosure",
)

DISCLOSURE_SLOT_ORDER = (
    "scenario-projections",
    "supporting-telemetry",
    "assumptions",
    "historical-telemetry",
    "sensitivity-analysis",
    "alternative-burns",
    "calculation-method",
    "evidence-and-provenance",
    "mission-definition",
)


@dataclass(frozen=True)
class ConsoleInstrumentView:
    kind: str
    label: str
    value: object | None
    unit_or_currency: str | None = None
    format_kind: str = "plain"
    detail: str = ""
    tone: str = "none"


@dataclass(frozen=True)
class MissionHeroView:
    definition: MissionDefinition
    current: MetricResult
    current_label: str
    current_format_kind: str
    milestone: MissionMilestone | None
    destination: MissionMilestone | None
    trajectory: MissionTrajectoryView
    margin: MissionMargin | None
    margin_applicability: str
    confidence: MissionConfidence
    burn_preview: str


@dataclass(frozen=True)
class FlightAnalysisView:
    trajectory: MissionTrajectoryView
    current: MetricResult
    current_label: str
    current_format_kind: str
    destination: MissionMilestone | None
    supporting: tuple[ConsoleInstrumentView, ...]
    evidence_note: str


@dataclass(frozen=True)
class EssentialTelemetryView:
    items: tuple[TelemetryItem, ...]


@dataclass(frozen=True)
class NextBurnView:
    state: str
    primary: RecommendationAssessment | None
    title: str
    summary: str
    safety_notices: tuple[str, ...]


@dataclass(frozen=True)
class DisclosureSectionView:
    slot: str
    id: str
    title: str
    telemetry: tuple[TelemetryItem, ...] = ()
    recommendations: tuple[RecommendationAssessment, ...] = ()
    lines: tuple[str, ...] = ()
    open_by_default: bool = False


@dataclass(frozen=True)
class MissionConsoleView:
    hero: MissionHeroView
    analysis: FlightAnalysisView
    essential: EssentialTelemetryView | None
    next_burn: NextBurnView
    disclosure: tuple[DisclosureSectionView, ...]

    @property
    def region_order(self) -> tuple[str, ...]:
        return tuple(
            region for region in REGION_ORDER
            if region != "essential-telemetry" or self.essential is not None
        )


class MissionConsoleModel:
    """Map one validated assessment into the universal console regions."""

    def build(
        self,
        definition: MissionDefinition,
        assessment: MissionAssessment,
    ) -> MissionConsoleView:
        if assessment.current_value is None:
            raise ValueError("Mission Console requires a current value")

        current_label, current_format = self._current_presentation(assessment)
        destination = next(
            (item for item in assessment.milestones if item.completes_mission),
            None,
        )
        confidence = assessment.confidence or MissionConfidence(
            "Insufficient", "Mission confidence is unavailable")
        trajectory = MissionTrajectoryView(
            state=assessment.trajectory_state,
            tone=assessment.trajectory_tone or "none",
            # Unknown is a legitimate permanent state when observed movement
            # is not declared; the Model never invents motion from forecasts.
            movement="unknown",
            destination_direction=definition.destination_direction,
            history=assessment.applicability.trajectory,
            forecast=assessment.applicability.forecast,
            intercept_at=assessment.eta,
            intercept_label=destination.label if destination else "",
            recent_change=assessment.delta_v,
            confidence_state=confidence.state,
            evidence_note=self._trajectory_evidence_note(assessment),
        )
        next_burn = self._next_burn(assessment, confidence)
        hero = MissionHeroView(
            definition=definition,
            current=assessment.current_value,
            current_label=current_label,
            current_format_kind=current_format,
            milestone=assessment.current_milestone,
            destination=destination,
            trajectory=trajectory,
            margin=assessment.mission_margin,
            margin_applicability=assessment.applicability.margin,
            confidence=confidence,
            burn_preview=(
                next_burn.primary.action_label or next_burn.primary.action
                if next_burn.primary is not None else ""
            ),
        )

        supporting: list[ConsoleInstrumentView] = []
        if assessment.applicability.delta_v != "not_applicable":
            supporting.append(ConsoleInstrumentView(
                kind="recent-movement",
                label="RECENT MOVEMENT",
                value=assessment.delta_v,
                detail=(assessment.delta_v.description
                        if assessment.delta_v else
                        "Recent movement is unavailable."),
            ))
        if assessment.current_milestone is not None:
            supporting.append(ConsoleInstrumentView(
                kind="milestone-completion",
                label="MILESTONE COMPLETION",
                value=assessment.current_milestone.completion,
                format_kind="percent",
                detail=assessment.current_milestone.label,
            ))
        if assessment.applicability.eta != "not_applicable":
            supporting.append(ConsoleInstrumentView(
                kind="intercept",
                label="EXPECTED INTERCEPT",
                value=assessment.eta,
                detail=(destination.label if destination else
                        "Mission destination"),
            ))

        essential_items = tuple(
            item for item in assessment.telemetry
            if item.display_region == "essential"
        )
        essential = (
            EssentialTelemetryView(essential_items)
            if essential_items else None
        )
        analysis = FlightAnalysisView(
            trajectory=trajectory,
            current=assessment.current_value,
            current_label=current_label,
            current_format_kind=current_format,
            destination=destination,
            supporting=tuple(supporting[:3]),
            evidence_note=trajectory.evidence_note,
        )
        return MissionConsoleView(
            hero=hero,
            analysis=analysis,
            essential=essential,
            next_burn=next_burn,
            disclosure=self._disclosure(definition, assessment),
        )

    @staticmethod
    def _current_presentation(
        assessment: MissionAssessment,
    ) -> tuple[str, str]:
        current = assessment.current_value
        if current is not None:
            for item in assessment.telemetry:
                if item.result.metric_id == current.metric_id:
                    return item.label, item.format_kind
        return "CURRENT POSITION", "plain"

    @staticmethod
    def _trajectory_evidence_note(assessment: MissionAssessment) -> str:
        notes = []
        if assessment.applicability.trajectory == "unavailable":
            notes.append("Observed trajectory history is unavailable.")
        elif assessment.applicability.trajectory == "not_applicable":
            notes.append("Observed trajectory history does not apply.")
        if assessment.applicability.forecast == "unavailable":
            notes.append("Forecast evidence is unavailable.")
        elif assessment.applicability.forecast == "not_applicable":
            notes.append("A forecast does not apply.")
        return " ".join(notes)

    @staticmethod
    def _next_burn(
        assessment: MissionAssessment,
        confidence: MissionConfidence,
    ) -> NextBurnView:
        primary = assessment.recommendations[0] \
            if assessment.recommendations else None
        if assessment.mission_complete:
            state = "mission-complete"
            title = "MISSION COMPLETE"
            summary = "The declared destination is currently achieved."
        elif primary is None:
            if confidence.state == "Insufficient":
                state = "insufficient-evidence"
                title = "INSUFFICIENT EVIDENCE"
                summary = "No safe burn can be declared from current evidence."
            else:
                state = "no-burn-required"
                title = "NO BURN REQUIRED"
                summary = "No improving action is declared for this assessment."
        elif primary.status == "suppressed":
            state = "suppressed"
            title = "BURN HELD"
            summary = primary.action
        elif primary.status == "advisory":
            state = "advisory"
            title = "ADVISORY"
            summary = primary.action
        elif primary.status != "available" \
                or not primary.action_label \
                or primary.amount is None \
                or primary.unit_or_currency is None:
            state = "insufficient-evidence"
            title = "INSUFFICIENT EVIDENCE"
            summary = "The declared recommendation is incomplete."
        else:
            state = "available"
            title = primary.action_label
            summary = primary.action

        safety = list(primary.limitations if primary else ())
        if confidence.state in ("Provisional", "Insufficient"):
            basis = assessment.confidence_basis or confidence.basis
            if basis:
                safety.append(basis)
        if state == "suppressed" and primary is not None:
            safety.insert(0, primary.action)
        return NextBurnView(
            state=state,
            primary=primary,
            title=title,
            summary=summary,
            safety_notices=tuple(dict.fromkeys(safety)),
        )

    @staticmethod
    def _disclosure(
        definition: MissionDefinition,
        assessment: MissionAssessment,
    ) -> tuple[DisclosureSectionView, ...]:
        groups: list[tuple[str, list[TelemetryItem]]] = []
        indexes: dict[str, int] = {}
        for item in assessment.telemetry:
            if item.display_region == "essential":
                continue
            title = item.display_group or f"{definition.label} telemetry"
            if title not in indexes:
                indexes[title] = len(groups)
                groups.append((title, []))
            groups[indexes[title]][1].append(item)

        sections = [
            DisclosureSectionView(
                slot="supporting-telemetry",
                id=f"supporting-telemetry-{index + 1}",
                title=title,
                telemetry=tuple(items),
            )
            for index, (title, items) in enumerate(groups)
        ]
        if len(assessment.recommendations) > 1:
            sections.append(DisclosureSectionView(
                slot="alternative-burns",
                id="alternative-burns",
                title=f"{definition.label} alternative burns",
                recommendations=assessment.recommendations[1:],
            ))
        evidence_lines = tuple(dict.fromkeys((
            assessment.confidence_basis,
            *assessment.limitations,
            f"{len(assessment.input_references)} metric input reference(s)",
            f"{len(assessment.evidence_references)} evidence reference(s)",
            f"{len(assessment.assumption_references)} assumption reference(s)",
        )))
        sections.append(DisclosureSectionView(
            slot="evidence-and-provenance",
            id="evidence-and-provenance",
            title=f"{definition.label} evidence and provenance",
            lines=tuple(line for line in evidence_lines if line),
        ))
        sections.append(DisclosureSectionView(
            slot="mission-definition",
            id="mission-definition",
            title=f"{definition.label} mission definition",
            lines=(definition.definition,),
        ))
        slot_rank = {slot: index for index, slot in enumerate(
            DISCLOSURE_SLOT_ORDER)}
        return tuple(sorted(
            sections,
            key=lambda section: slot_rank[section.slot],
        ))
