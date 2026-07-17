"""
Mission status — 000-core-domain-model.md §8.

Three strictly separated steps:

    1. The owning domain calculates the metric  (registry.dispatch)
    2. Core evaluates mission status             (evaluate_mission_status)
    3. AI may explain the result but cannot determine it  (not here)

Step 3 is enforced by absence, the same way `metrics.py` enforces "AI
never calculates": nothing in this module accepts or calls a
`ModelAdapter`. A model-authored explanation of *why* a Mission is
off track is a `Claim` (evidence.py) that some other code path may
attach to the same subject — it is never an input to, or a substitute
for, the comparison below.
"""

from __future__ import annotations

from .entities import EntityProjection, Mission
from .metrics import MetricRegistry, MetricRequest, MetricResult
from .scope import Subject


def request_for_mission(mission: Mission, scope: Subject, as_of: float,
                         horizon: tuple[float, float] | None = None) -> MetricRequest:
    """Step 1's request shape. Dispatching it is the caller's job
    (`registry.dispatch(request)`), kept separate so evaluation (step
    2) is testable without a real registry or provider."""
    return MetricRequest(metric_id=mission.target_metric, scope=scope, as_of=as_of, horizon=horizon)


def evaluate_mission_status(mission: Mission, result: MetricResult) -> str | None:
    """Step 2: a pure comparison of an already-retrieved `MetricResult`
    against the Mission's declared policy. Never fabricates a status —
    returns `None` when the Mission has no declared target, or when the
    metric itself is not `available`/`stale`.

    `unavailable`, `unsupported`, and `error` are deliberately treated
    identically here (no status computable): distinguishing "we don't
    support this" from "something broke" is a rendering concern, not an
    evaluation one — the underlying distinction is never lost, because
    the full `MetricResult` (including its exact `status`) is always
    returned alongside, not discarded.

    **The banding below (within-tolerance = on_track, within 2x =
    at_risk, beyond = off_track) is a provisional V1 implementation
    policy, not permanent product logic.** `000` §8 deliberately does
    not pin an exact formula; this is the simplest one that satisfies
    "never fabricate a status," chosen so RFC-001 has *a* concrete,
    testable rule to ship — not a considered product decision about
    what RAG banding should mean. Replacing it should not require
    touching anything outside this function."""
    if mission.status in ("achieved", "abandoned"):
        return mission.status
    if result.status not in ("available", "stale"):
        return None
    if result.value is None:
        return None

    value = result.value
    if mission.target_range is not None:
        lo, hi = mission.target_range
        on_target = lo <= value <= hi
        distance = 0.0 if on_target else min(abs(value - lo), abs(value - hi))
        tolerance = mission.tolerance or 0.0
    elif mission.target_value is not None:
        tolerance = mission.tolerance or 0.0
        distance = abs(value - mission.target_value)
        on_target = distance <= tolerance
    else:
        return None  # no declared target — never invent a status

    if on_target:
        return "on_track"
    if tolerance and distance <= tolerance * 2:
        return "at_risk"
    return "off_track"


def get_mission_status(mission_id: str, entities: EntityProjection, registry: MetricRegistry,
                        scope: Subject, as_of: float, horizon: tuple[float, float] | None = None,
                        ) -> tuple[str | None, MetricResult | None]:
    """Convenience orchestration of steps 1 and 2 together.

    Takes `mission_id` + the `EntityProjection` to read it from, rather
    than a `Mission` object a caller might be holding from an earlier,
    now-stale `declare_mission()`/`update` call — `Mission` objects are
    immutable snapshots (constitutional invariant 2: state lives in the
    log, not a cached object), so the only way to guarantee this
    function evaluates against *current* Mission policy is to look it
    up fresh, here, from the same projection the caller is using for
    everything else. Returns `(None, None)` if `mission_id` doesn't
    resolve — never a crash, never a fabricated status."""
    mission = entities.missions.get(mission_id)
    if mission is None:
        return None, None
    request = request_for_mission(mission, scope, as_of, horizon=horizon)
    result = registry.dispatch(request)
    return evaluate_mission_status(mission, result), result
