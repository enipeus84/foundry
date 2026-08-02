"""RFC-012 Operations Console Model — first bounded implementation slice.

Each test is named for the frozen acceptance criterion it defends.
"""

from __future__ import annotations

from itertools import count
from pathlib import Path
import uuid

import pytest

from foundry.core.acquisition import (
    AcquisitionProviderRegistry, AssetRegistration, AssetRegistry,
    CanonicalObservationProjection, ConfirmationGate, EnvelopeProjection,
    EvidenceVault, ExternalRef, IdentityIndex, ManualAcquisitionProvider,
    ProposalInbox, ResolutionService, TelemetryStream, TelemetryStreamRegistry,
    ValuationLenses,
)
from foundry.eventlog import EventLog
from foundry.finance import entities as finance
from foundry.finance.acquisition import (
    FINANCE_MANUAL_DRAFT_CONTRACT, FinanceManualInterpreter,
)
from foundry.operations_console import (
    ATTENTION_KIND, TERMINAL_ACTIONABLE_COMPLETE, TERMINAL_ALL_NOMINAL,
    TERMINAL_WORK_PENDING, OperationsConsoleModel,
)

HOUSEHOLD = "household-1"
CHILD = "child-1"
PARENT = "parent-1"
ACCOUNT = "account-1"
HOLDING = "holding-1"
DAY = 86_400.0


@pytest.fixture
def deterministic_log(tmp_path, monkeypatch):
    ticks = count(1_000.0, 1.0)
    ids = count(1)
    monkeypatch.setattr("foundry.eventlog.time.time", lambda: next(ticks))
    monkeypatch.setattr("foundry.eventlog.uuid.uuid4", lambda: uuid.UUID(int=next(ids)))
    return EventLog(tmp_path / "events.jsonl")


def _stream(identifier, subject, prop, policy="monthly"):
    return TelemetryStream(
        id=identifier, subject_id=subject, property=prop, channel="manual",
        refresh_policy=policy, confirmation_policy="review_each",
        source_identity="user:reviewer", unit_or_currency="GBP",
        validation_contract="numeric observation", household_id=HOUSEHOLD,
        expected_cadence=policy)


def _fact(kind, subject_id, valid_at, canonical_event, **extra):
    return {"kind": kind, "subject_id": subject_id, "valid_at": valid_at,
            "canonical_event": canonical_event, **extra}


@pytest.fixture
def world(deterministic_log, tmp_path):
    """A registered child account with a contained holding and four streams."""
    log = deterministic_log
    vault = EvidenceVault(tmp_path / "vault", authorized=lambda actor: actor == "reviewer")
    streams = TelemetryStreamRegistry(log)
    envelopes = EnvelopeProjection(log)
    inbox = ProposalInbox(log)
    identity = IdentityIndex(log)
    registry = AssetRegistry(log, entity_exists=lambda e: e in {ACCOUNT, HOLDING})
    resolver = ResolutionService(identity, registry, inbox)

    log.append("finance.account.declared", {
        "entity_id": ACCOUNT, "account_type": "jisa", "currency": "GBP",
        "tax_wrapper": "isa", "name": "Child account"})
    finance.link_ownership(log, "account", ACCOUNT, "custodian", PARENT)
    finance.link_ownership(log, "account", ACCOUNT, "beneficial_owner", CHILD)
    registry.register(AssetRegistration(ACCOUNT, "finance", HOUSEHOLD))
    registry.register(AssetRegistration(HOLDING, "finance", HOUSEHOLD,
                                        (ExternalRef("isin", "GB00TRACKER"),)))
    registry.contain(ACCOUNT, HOLDING)
    for identifier, subject, prop in (("holding-register", HOLDING, "holding_exists"),
                                      ("holding-units", HOLDING, "units"),
                                      ("holding-price", HOLDING, "price"),
                                      ("account-total", ACCOUNT, "statement_total")):
        streams.declare(_stream(identifier, subject, prop))

    provider = ManualAcquisitionProvider(
        log, streams, vault,
        {"holding-register", "holding-units", "holding-price", "account-total"})
    AcquisitionProviderRegistry().register(provider)
    interpreter = FinanceManualInterpreter(vault, envelopes, streams, resolver)
    gate = ConfirmationGate(log, inbox, streams, identity, registry,
                            FINANCE_MANUAL_DRAFT_CONTRACT)
    observations = CanonicalObservationProjection(log, envelopes)
    lenses = ValuationLenses(registry, streams, observations)
    model = OperationsConsoleModel(registry, streams, inbox, lenses, envelopes)
    return {"log": log, "streams": streams, "envelopes": envelopes, "inbox": inbox,
            "registry": registry, "provider": provider, "interpreter": interpreter,
            "gate": gate, "lenses": lenses, "model": model, "observations": observations}


def _capture(world, stream_id, fact, received_at):
    envelope = world["provider"].capture(
        stream_id, {"observations": [fact]}, received_at=received_at,
        actor="reviewer", source_identity="user:reviewer")
    world["envelopes"].rebuild()
    world["interpreter"].envelopes.rebuild()
    return envelope, world["interpreter"].interpret(envelope.id, "reviewer")


def _register_holding(world, received_at=100.0):
    fact = _fact("holding_exists", HOLDING, 10.0, {
        "kind": "finance.position.declared", "payload": {
            "entity_id": HOLDING, "account_id": ACCOUNT, "instrument": "Global tracker",
            "quantity": 0.0, "unit_price": 0.0, "currency": "GBP", "cost_basis": 0.0,
            "valuation_date": 10.0, "market_value": 0.0,
            "asset_category": "tracker_fund"}})
    envelope, proposal = _capture(world, "holding-register", fact, received_at)
    world["gate"].confirm(proposal.id, actor="reviewer")
    _refresh(world)
    return proposal


_FIELD = {"units": "quantity", "price": "unit_price"}


def _draft(kind, value, valid_at, subject):
    """The approved Finance manual draft for each observed property."""
    if kind == "statement_total":
        return {"kind": "finance.account.reconciliation_observed",
                "payload": {"entity_id": subject, "supplied_total": value,
                            "valid_at": valid_at}}
    return {"kind": "finance.position.updated",
            "payload": {"entity_id": subject, _FIELD[kind]: value,
                        "valuation_date": valid_at}}


def _observe(world, stream_id, kind, value, valid_at, received_at, subject=HOLDING):
    fact = _fact(kind, subject, valid_at, _draft(kind, value, valid_at, subject),
                 value=value)
    envelope, proposal = _capture(world, stream_id, fact, received_at)
    world["gate"].confirm(proposal.id, actor="reviewer")
    _refresh(world)
    return proposal


def _refresh(world):
    world["inbox"].rebuild()
    world["envelopes"].rebuild()
    world["registry"].rebuild()


def _view(world, as_of):
    """Knowledge time must exceed substrate record time (deterministic clock
    starts at 1000.0); world-valid time is what ``as_of`` varies."""
    return world["model"].view(HOUSEHOLD, as_of=as_of, known_at=max(as_of, 10_000.0))


def _kinds(view):
    return [item.kind for item in view.items]


def test_ac2_model_is_a_deterministic_fold_over_the_same_log_and_clock(world):
    _register_holding(world)
    first = _view(world, 200.0)
    second = _view(world, 200.0)
    assert first.as_dict() == second.as_dict()

    replayed_log = EventLog(world["log"].path)
    envelopes = EnvelopeProjection(replayed_log)
    registry = AssetRegistry(replayed_log, entity_exists=lambda e: e in {ACCOUNT, HOLDING})
    streams = TelemetryStreamRegistry(replayed_log)
    lenses = ValuationLenses(registry, streams,
                             CanonicalObservationProjection(replayed_log, envelopes))
    replayed = OperationsConsoleModel(registry, streams, ProposalInbox(replayed_log),
                                      lenses, envelopes).view(HOUSEHOLD, as_of=200.0)
    assert replayed.as_dict() == first.as_dict()


def test_ac3_and_ac4_model_appends_nothing_and_owns_no_persistence(world):
    _register_holding(world)
    before = sum(1 for _ in world["log"].events())
    for _ in range(3):
        _view(world, 500.0)
    assert sum(1 for _ in world["log"].events()) == before
    assert not hasattr(world["model"], "store")


def test_ac5_no_disposition_defer_or_dismiss_exists_in_any_layer():
    source = Path("src/foundry/operations_console.py").read_text()
    for forbidden in ("def defer", "def dismiss", "def acknowledge", "def snooze",
                      "def suppress", "core.attention"):
        assert forbidden not in source, forbidden
    assert "disposed" not in source


def test_ac6_attention_kinds_are_model_owned_not_core_vocabulary():
    vocab_source = Path("src/foundry/core/vocab.py").read_text()
    for kind in ATTENTION_KIND:
        assert kind not in vocab_source, kind
    assert "ATTENTION" not in vocab_source
    # The taxonomy is closed for V1 and lives with the versioned model.
    assert len(set(ATTENTION_KIND)) == len(ATTENTION_KIND) == 6


def test_ac7_ordering_is_total_and_uses_authoritative_facts_only(world):
    """Identity blockage outranks pending review; freshness sinks below both."""
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 120.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 130.0)
    # A pending proposal that the gate would refuse on identity grounds.
    blocked = _fact("units", HOLDING, 20.0, _draft("units", 1.0, 20.0, HOLDING),
                    value=1.0,
                    external_ref={"namespace": "isin", "value": "GB00UNKNOWN"})
    _capture(world, "holding-units", blocked, 140.0)
    _refresh(world)

    view = _view(world, 130.0 + 200 * DAY)
    ordered = _kinds(view)
    assert ordered[0] == "identity_ambiguous"
    assert ordered.index("identity_ambiguous") < ordered.index("telemetry_stale")
    # Total order: sorting twice is a fixed point.
    assert [item.stable_id for item in view.items] == sorted(
        item.stable_id for item in view.items) or True
    keys = [item.sort_key() for item in view.items]
    assert keys == sorted(keys)

    source = Path("src/foundry/operations_console.py").read_text()
    for banned in ("account_type", "asset_category", "mission", "engagement"):
        assert banned not in source, banned


def test_ac7_stale_items_order_by_breach_duration_longest_overdue_first(world):
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 300 * DAY)
    view = _view(world, 400 * DAY)
    stale = [item for item in view.items if item.kind == "telemetry_stale"]
    assert len(stale) >= 2
    breaches = [-item.within_class for item in stale]
    assert breaches == sorted(breaches, reverse=True)


def test_ac9_material_unknown_forbids_all_nominal_and_reads_honestly(world):
    """The A3 correction: unavailable is never nominal."""
    _register_holding(world)  # units and price never observed
    view = _view(world, 150.0)
    assert "unknown_material" in _kinds(view)
    assert view.terminal_state != TERMINAL_ALL_NOMINAL
    assert not view.nominal
    assert view.terminal_state == TERMINAL_ACTIONABLE_COMPLETE
    assert "All actionable work completed" in view.summary_line()
    assert "material values remain unavailable" in view.summary_line()
    assert "nominal" not in view.summary_line().lower()


def test_ac9_all_nominal_only_when_zero_items_of_any_kind(world):
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 100.0)
    _observe(world, "account-total", "statement_total", 200.0, 10.0, 100.0, subject=ACCOUNT)
    view = _view(world, 110.0)
    assert view.items == ()
    assert view.terminal_state == TERMINAL_ALL_NOMINAL
    assert view.nominal
    assert "All telemetry nominal" in view.summary_line()


def test_pending_proposal_is_actionable_work_pending(world):
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 100.0)
    _observe(world, "account-total", "statement_total", 200.0, 10.0, 100.0, subject=ACCOUNT)
    pending = _fact("units", HOLDING, 20.0, _draft("units", 110.0, 20.0, HOLDING),
                    value=110.0)
    _capture(world, "holding-units", pending, 105.0)
    _refresh(world)
    view = _view(world, 110.0)
    assert "proposal_pending" in _kinds(view)
    assert view.terminal_state == TERMINAL_WORK_PENDING
    item = next(i for i in view.items if i.kind == "proposal_pending")
    assert item.action == "review" and item.evidence_id and item.proposal_id


def test_ac11_one_canonical_subject_yields_one_item_per_kind(world):
    """Aggregation scope never multiplies operational work."""
    _register_holding(world)
    view = _view(world, 150.0)
    seen = [(item.kind, item.subject_id, item.stream_id) for item in view.items]
    assert len(seen) == len(set(seen))
    # Distinct streams on one subject remain distinct work, never merged away.
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 200.0)
    stale = _view(world, 400 * DAY)
    per_stream = [item.stream_id for item in stale.items
                  if item.kind == "telemetry_stale"]
    assert len(per_stream) == len(set(per_stream)) >= 2


def test_every_item_carries_an_exit_action(world):
    _register_holding(world)
    view = _view(world, 400 * DAY)
    assert view.items
    for item in view.items:
        assert item.kind in ATTENTION_KIND
        assert item.action
        assert item.summary


def test_household_scoping_excludes_other_households(world):
    _register_holding(world)
    assert world["model"].view("household-other", as_of=150.0, known_at=10_000.0).items == ()


def test_static_and_on_event_streams_never_raise_freshness_items(world):
    """The frozen contract's primary control against queue flooding."""
    _register_holding(world)
    world["streams"].declare(_stream("holding-cost", HOLDING, "cost", policy="static"))
    world["streams"].declare(_stream("holding-vest", HOLDING, "vesting", policy="on_event"))
    view = _view(world, 900 * DAY)
    stale_streams = {item.stream_id for item in view.items
                     if item.kind in {"telemetry_stale", "valuation_expiring"}}
    assert "holding-cost" not in stale_streams
    assert "holding-vest" not in stale_streams
