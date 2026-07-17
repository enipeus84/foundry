"""Unit tests: the Metric Provider contract and Metric Registry
(000 §13)."""

import time

import pytest

from foundry.core import grammar
from foundry.core.entities import EntityProjection, declare_mission
from foundry.core.mission_evaluation import evaluate_mission_status, get_mission_status
from foundry.core.metrics import MetricRegistry, MetricRequest, MetricResult
from foundry.core.scope import Subject
from foundry.errors import DuplicateMetricError


class _MockProvider:
    """A deterministic, in-memory provider — stands in for a domain's
    real calculation code without needing one to exist yet."""

    def __init__(self, metric_id, value, status="available", version="v1"):
        self.metric_id = metric_id
        self.value = value
        self.status = status
        self.version = version
        self.calls = 0

    def owned_metric_ids(self):
        return frozenset({self.metric_id})

    def calculate(self, request):
        self.calls += 1
        return MetricResult(
            metric_id=request.metric_id, value=self.value, unit_or_currency="GBP",
            scope=request.scope, as_of=request.as_of, status=self.status,
            calculation_version=self.version, input_references=("evt-1",),
        )


def test_register_and_dispatch(kernel):
    registry = MetricRegistry()
    provider = _MockProvider("mock.net_worth", 1000.0)
    registry.register(provider)

    result = registry.dispatch(MetricRequest(
        metric_id="mock.net_worth", scope=Subject("party", "p1"), as_of=time.time()))
    assert result.status == "available"
    assert result.value == 1000.0
    assert provider.calls == 1


def test_unknown_metric_fails_closed_not_an_exception(kernel):
    """Unknown metric_id returns status: unsupported — never an
    exception indistinguishable from a bug, never a fabricated value."""
    registry = MetricRegistry()
    result = registry.dispatch(MetricRequest(
        metric_id="nobody.owns_this", scope=Subject("party", "p1"), as_of=time.time()))
    assert result.status == "unsupported"
    assert result.value is None


def test_duplicate_registration_fails_closed(kernel):
    registry = MetricRegistry()
    registry.register(_MockProvider("mock.net_worth", 1000.0))
    with pytest.raises(DuplicateMetricError):
        registry.register(_MockProvider("mock.net_worth", 2000.0))
    # The first registration is untouched:
    result = registry.dispatch(MetricRequest(
        metric_id="mock.net_worth", scope=Subject("party", "p1"), as_of=time.time()))
    assert result.value == 1000.0


def test_registration_order_does_not_alter_results(kernel):
    """Ownership is by declared metric_id, never by which provider
    registered first or last — there is no precedence to depend on."""
    registry_a, registry_b = MetricRegistry(), MetricRegistry()
    p1, p2 = _MockProvider("mock.x", 1.0), _MockProvider("mock.y", 2.0)

    registry_a.register(p1)
    registry_a.register(p2)
    registry_b.register(p2)
    registry_b.register(p1)

    req_x = MetricRequest(metric_id="mock.x", scope=Subject("party", "p1"), as_of=1.0)
    req_y = MetricRequest(metric_id="mock.y", scope=Subject("party", "p1"), as_of=1.0)
    assert registry_a.dispatch(req_x).value == registry_b.dispatch(req_x).value == 1.0
    assert registry_a.dispatch(req_y).value == registry_b.dispatch(req_y).value == 2.0


def test_registry_has_no_business_logic_only_routing():
    """A registry with zero providers routes zero metrics — it
    computes nothing itself."""
    registry = MetricRegistry()
    assert registry.owned_metric_ids() == frozenset()


def test_metric_result_rejects_status_outside_vocabulary():
    from foundry.errors import VocabularyError
    with pytest.raises(VocabularyError):
        MetricResult(metric_id="x", value=1.0, unit_or_currency=None,
                      scope=Subject("party", "p1"), as_of=1.0,
                      status="not_a_real_status", calculation_version="v1")


def test_no_model_adapter_import_in_metrics_module():
    """'AI must never calculate a deterministic metric' is enforced by
    absence: the dispatch module never imports foundry.models."""
    import ast
    import inspect

    import foundry.core.metrics as metrics_module
    tree = ast.parse(inspect.getsource(metrics_module))
    imported_modules = {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "foundry.models" not in imported_modules
    assert "foundry.kernel" not in imported_modules


# ------------------------------------------------------------- mission status

def test_mission_status_on_track_within_tolerance():
    mission = type("M", (), {"status": "active", "target_range": None,
                              "target_value": 100.0, "tolerance": 10.0})()
    result = MetricResult(metric_id="x", value=105.0, unit_or_currency=None,
                           scope=Subject("mission", "m1"), as_of=1.0,
                           status="available", calculation_version="v1")
    assert evaluate_mission_status(mission, result) == "on_track"


def test_mission_status_off_track_far_from_target():
    mission = type("M", (), {"status": "active", "target_range": None,
                              "target_value": 100.0, "tolerance": 10.0})()
    result = MetricResult(metric_id="x", value=1.0, unit_or_currency=None,
                           scope=Subject("mission", "m1"), as_of=1.0,
                           status="available", calculation_version="v1")
    assert evaluate_mission_status(mission, result) == "off_track"


def test_mission_status_never_fabricated_without_a_target(kernel):
    mission = declare_mission(kernel.log, "No target set")  # target_metric="" by default
    result = MetricResult(metric_id="", value=42.0, unit_or_currency=None,
                           scope=Subject("mission", mission.id), as_of=1.0,
                           status="available", calculation_version="v1")
    assert evaluate_mission_status(mission, result) is None


def test_mission_status_never_fabricated_when_metric_unsupported(kernel):
    mission = declare_mission(kernel.log, "Net worth goal", target_metric="mock.net_worth",
                               target_value=1000.0, tolerance=100.0)
    entities = EntityProjection(kernel.log)
    registry = MetricRegistry()  # nothing registered
    status, result = get_mission_status(mission.id, entities, registry,
                                         Subject("mission", mission.id), time.time())
    assert result.status == "unsupported"
    assert status is None


def test_mission_status_unknown_mission_id_returns_none_not_a_crash(kernel):
    entities = EntityProjection(kernel.log)
    registry = MetricRegistry()
    status, result = get_mission_status("no-such-mission", entities, registry,
                                         Subject("mission", "no-such-mission"), time.time())
    assert status is None and result is None


def test_mission_status_end_to_end_domain_calculates_core_evaluates(kernel):
    """The three-step split (000 §8), exercised together: a mock
    domain calculates, Core evaluates — no AI is involved anywhere in
    this path."""
    mission = declare_mission(kernel.log, "Net worth goal", target_metric="mock.net_worth",
                               target_value=1000.0, tolerance=100.0)
    entities = EntityProjection(kernel.log)
    registry = MetricRegistry()
    registry.register(_MockProvider("mock.net_worth", 1050.0))

    status, result = get_mission_status(mission.id, entities, registry,
                                         Subject("mission", mission.id), time.time())
    assert status == "on_track"
    assert result.value == 1050.0


def test_mission_status_reflects_current_not_stale_mission_state(kernel):
    """get_mission_status() reads the Mission fresh from `entities` by
    id, not from a possibly-stale object the caller might be holding —
    a target set *after* declare_mission() returns is still honoured."""
    mission = declare_mission(kernel.log, "Flexible target")  # no target yet
    # Simulate a later refinement of the mission's target via a fresh
    # core.mission.updated event, appended after the stale `mission`
    # object above was returned:
    grammar.update(kernel.log, "core", "mission", mission.id,
                    {"target_metric": "mock.net_worth", "target_value": 500.0,
                     "tolerance": 50.0}, reason="target set")

    entities = EntityProjection(kernel.log)
    registry = MetricRegistry()
    registry.register(_MockProvider("mock.net_worth", 500.0))

    status, result = get_mission_status(mission.id, entities, registry,
                                         Subject("mission", mission.id), time.time())
    assert status == "on_track"  # only possible if the *current* target was used
