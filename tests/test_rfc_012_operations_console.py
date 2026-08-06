"""RFC-012 Operations Console Model — first bounded implementation slice.

Each test is named for the frozen acceptance criterion it defends.
"""

from __future__ import annotations

from itertools import count
from pathlib import Path
import uuid

import pytest

from foundry.core.acquisition import (
    AcquisitionError, AcquisitionProviderRegistry, AssetRegistration, AssetRegistry,
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
    TERMINAL_WORK_PENDING, UNIMPLEMENTABLE_IN_PHASE_1A, AttentionItem,
    OperationsConsoleModel, attention_identity,
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
    return {"log": log, "vault": vault, "streams": streams, "envelopes": envelopes, "inbox": inbox,
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


def _retire(world, stream_id):
    world["log"].append("core.telemetry_stream.retired", {
        "stream_id": stream_id, "reason": "retired for test", "retired_at": 1.0,
    })
    world["streams"].rebuild()


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
    keys = [item.sort_key() for item in view.items]
    assert keys == sorted(keys), "view must be returned already ordered"

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


def test_rfc_015_phase_3_retirement_suppresses_only_the_retired_target(world):
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 100.0)
    _observe(world, "account-total", "statement_total", 200.0, 10.0, 100.0, subject=ACCOUNT)
    pending = _pending(world, "holding-units", 110.0, 20.0, 105.0)
    _retire(world, "holding-units")

    view = _view(world, 400 * DAY)

    assert pending.id not in {item.proposal_id for item in view.items}
    assert "holding-units" not in {item.stream_id for item in view.items}
    assert "holding-price" in {item.stream_id for item in view.items}
    assert world["streams"].streams["holding-units"].id == "holding-units"
    assert "holding-units" in world["streams"].retired


def test_rfc_015_phase_3_all_retired_targets_are_operationally_quiet_but_replayable(world):
    _register_holding(world)
    _observe(world, "holding-units", "units", 100.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 2.0, 10.0, 100.0)
    _observe(world, "account-total", "statement_total", 200.0, 10.0, 100.0, subject=ACCOUNT)
    for stream_id in ("holding-register", "holding-units", "holding-price", "account-total"):
        _retire(world, stream_id)

    first = _view(world, 400 * DAY)
    replayed_log = EventLog(world["log"].path)
    envelopes = EnvelopeProjection(replayed_log)
    registry = AssetRegistry(replayed_log, entity_exists=lambda e: e in {ACCOUNT, HOLDING})
    streams = TelemetryStreamRegistry(replayed_log)
    replayed = OperationsConsoleModel(
        registry, streams, ProposalInbox(replayed_log),
        ValuationLenses(registry, streams, CanonicalObservationProjection(replayed_log, envelopes)),
        envelopes).view(HOUSEHOLD, as_of=400 * DAY, known_at=10_000.0)

    assert first.items == ()
    assert first.nominal and first.retired_stream_count == 4
    assert "retired streams intentionally suppressed" in first.summary_line()
    assert replayed.as_dict() == first.as_dict()
    assert len(streams.streams) == 4 and streams.retired == {
        "holding-register", "holding-units", "holding-price", "account-total"}


def test_rfc_015_phase_3_retirement_refuses_pending_confirmation(world):
    _register_holding(world)
    proposal = _pending(world, "holding-units", 10.0, 20.0, 110.0)
    _retire(world, "holding-units")

    with pytest.raises(AcquisitionError, match="proposal target is retired"):
        world["gate"].confirm(proposal.id, actor="reviewer")


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


# --- SAFE-33 remediation regressions -----------------------------------------


def _pending(world, stream_id, value, valid_at, received_at, external_ref=None):
    """Capture a proposal and leave it unresolved in the inbox."""
    extra = {"external_ref": external_ref} if external_ref else {}
    fact = _fact("units", HOLDING, valid_at, _draft("units", value, valid_at, HOLDING),
                 value=value, **extra)
    envelope = world["provider"].capture(
        stream_id, {"observations": [fact]}, received_at=received_at,
        actor="reviewer", source_identity="user:reviewer")
    world["envelopes"].rebuild()
    world["interpreter"].envelopes.rebuild()
    proposal = world["interpreter"].interpret(envelope.id, "reviewer")
    _refresh(world)
    return proposal


def test_safe_33_01_two_pending_proposals_on_one_stream_produce_two_items(world):
    _register_holding(world)
    first = _pending(world, "holding-units", 10.0, 20.0, 110.0)
    second = _pending(world, "holding-units", 11.0, 21.0, 120.0)
    assert first.id != second.id

    view = _view(world, 130.0)
    pending = [item for item in view.items if item.kind == "proposal_pending"]
    assert len(pending) == 2, "distinct proposals must never collapse"
    assert {item.proposal_id for item in pending} == {first.id, second.id}


def test_safe_33_01_two_ambiguous_proposals_on_one_stream_produce_two_items(world):
    _register_holding(world)
    first = _pending(world, "holding-units", 10.0, 20.0, 110.0,
                     external_ref={"namespace": "isin", "value": "GB00UNKNOWN1"})
    second = _pending(world, "holding-units", 11.0, 21.0, 120.0,
                      external_ref={"namespace": "isin", "value": "GB00UNKNOWN2"})
    view = _view(world, 130.0)
    ambiguous = [item for item in view.items if item.kind == "identity_ambiguous"]
    assert len(ambiguous) == 2
    assert {item.proposal_id for item in ambiguous} == {first.id, second.id}


def test_safe_33_01_insertion_order_does_not_change_the_queue(world):
    """Dedup and ordering must not depend on projection iteration order."""
    _register_holding(world)
    _pending(world, "holding-units", 10.0, 20.0, 110.0)
    _pending(world, "holding-units", 11.0, 21.0, 120.0)
    baseline = _view(world, 130.0).as_dict()

    inbox = world["inbox"]
    inbox.proposals = dict(reversed(list(inbox.proposals.items())))
    assert _view(world, 130.0).as_dict() == baseline

    registry = world["registry"]
    registry.registrations = dict(reversed(list(registry.registrations.items())))
    streams = world["streams"]
    streams.streams = dict(reversed(list(streams.streams.items())))
    assert _view(world, 130.0).as_dict() == baseline


def test_safe_33_01_repeated_folding_is_byte_identical(world):
    _register_holding(world)
    _pending(world, "holding-units", 10.0, 20.0, 110.0)
    _pending(world, "holding-units", 11.0, 21.0, 120.0)
    views = [_view(world, 130.0).as_dict() for _ in range(5)]
    assert all(view == views[0] for view in views)


def test_safe_33_01_aggregation_scope_still_does_not_multiply_items(world):
    """One canonical subject and stream yields one item however many scopes."""
    _register_holding(world)
    view = _view(world, 400 * DAY)
    identities = [item.identity for item in view.items]
    assert len(identities) == len(set(identities))


def test_safe_33_02_and_04_unimplementable_kinds_are_never_emitted(world):
    """Phantom float divergence and text-inferred expiry cannot reach the queue."""
    assert UNIMPLEMENTABLE_IN_PHASE_1A == {"reconciliation_divergence",
                                           "valuation_expiring"}
    _register_holding(world)
    # 3 x 0.1 != 0.3 in IEEE-754; an exact test would raise a permanent item.
    _observe(world, "holding-units", "units", 3.0, 10.0, 100.0)
    _observe(world, "holding-price", "price", 0.1, 10.0, 100.0)
    _observe(world, "account-total", "statement_total", 0.3, 10.0, 100.0, subject=ACCOUNT)
    view = _view(world, 110.0)
    assert 3.0 * 0.1 != 0.3, "the float hazard this test exists for"
    assert "reconciliation_divergence" not in _kinds(view)
    assert view.terminal_state == TERMINAL_ALL_NOMINAL


def test_safe_33_04_free_text_property_cannot_trigger_valuation_expiry(world):
    """No naming convention, no parser: text never selects an attention kind."""
    _register_holding(world)
    names = ("valuation", "estimate", "valuation_gbp", "market_estimate")
    ids = {f"s-{name}" for name in names}
    for name in names:
        world["streams"].declare(_stream(f"s-{name}", HOLDING, name))
    provider = ManualAcquisitionProvider(world["log"], world["streams"],
                                         world["vault"], ids)
    original = world["provider"]
    world["provider"] = provider
    try:
        for name in names:
            _observe(world, f"s-{name}", "units", 1.0, 10.0, 100.0)
    finally:
        world["provider"] = original
    view = _view(world, 400 * DAY)
    assert "valuation_expiring" not in _kinds(view)
    assert any(item.kind == "telemetry_stale" for item in view.items)


def test_safe_33_03_reconciliation_class_orders_by_stable_identifier(world):
    """Governor Phase 1A ruling: no invented timestamp; stable id ascending."""
    items = [AttentionItem(kind="reconciliation_divergence", subject_id=subject,
                           action="investigate", summary="", class_rank=3, sub_rank=0)
             for subject in ("subject-b", "subject-a", "subject-c")]
    ordered = sorted(items, key=lambda item: item.sort_key())
    assert [item.stable_id for item in ordered] == sorted(item.stable_id for item in items)
    assert {item.within_class for item in items} == {0.0}, "no temporal field is invented"


def test_safe_33_05_ordering_is_a_genuine_total_order_under_adversarial_ties():
    """Hand-built items with deliberate ties; the order must be strict."""
    tied = [
        AttentionItem(kind="telemetry_stale", subject_id="s1", action="capture",
                      summary="", stream_id="b", class_rank=4, within_class=-10.0),
        AttentionItem(kind="telemetry_stale", subject_id="s1", action="capture",
                      summary="", stream_id="a", class_rank=4, within_class=-10.0),
        AttentionItem(kind="unknown_material", subject_id="s1", action="capture",
                      summary="", class_rank=2),
        AttentionItem(kind="proposal_pending", subject_id="s1", action="review",
                      summary="", stream_id="a", proposal_id="p2",
                      class_rank=1, sub_rank=1, within_class=5.0),
        AttentionItem(kind="identity_ambiguous", subject_id="s1", action="resolve",
                      summary="", stream_id="a", proposal_id="p1",
                      class_rank=1, sub_rank=0, within_class=5.0),
    ]
    ordered = sorted(tied, key=lambda item: item.sort_key())
    assert [item.kind for item in ordered][:3] == [
        "identity_ambiguous", "proposal_pending", "unknown_material"]
    keys = [item.sort_key() for item in ordered]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys), "ties must be broken, never left equal"
    # Order is independent of the input permutation.
    assert [item.stable_id for item in sorted(reversed(tied),
                                              key=lambda item: item.sort_key())] == \
           [item.stable_id for item in ordered]


def test_safe_33_06_stable_identifier_resists_delimiter_collision():
    """("a|b", "c") and ("a", "b|c") must not become the same identifier."""
    left = AttentionItem(kind="telemetry_stale", subject_id="a|b", action="capture",
                         summary="", stream_id="c")
    right = AttentionItem(kind="telemetry_stale", subject_id="a", action="capture",
                          summary="", stream_id="b|c")
    assert left.identity != right.identity
    assert left.stable_id != right.stable_id
    assert left.sort_key() != right.sort_key()
    # Deterministic across calls and independent of process hash seeding.
    assert left.stable_id == AttentionItem(
        kind="telemetry_stale", subject_id="a|b", action="capture",
        summary="different text", stream_id="c").stable_id


def test_safe_33_06_identity_is_per_source_not_universal():
    proposal = attention_identity("proposal_pending", subject_id="subj",
                                  stream_id="stream", proposal_id="p1")
    other = attention_identity("proposal_pending", subject_id="subj",
                               stream_id="stream", proposal_id="p2")
    assert proposal != other, "proposal identity distinguishes proposals"
    stream = attention_identity("telemetry_stale", subject_id="subj",
                                stream_id="s1", proposal_id=None)
    assert stream != attention_identity("telemetry_stale", subject_id="subj",
                                        stream_id="s2", proposal_id=None)
    unknown = attention_identity("unknown_material", subject_id="subj",
                                 stream_id=None, proposal_id=None)
    assert unknown == ("unknown_material", "subj")


def test_safe_33_06_summary_line_never_hides_a_material_unknown(world):
    _register_holding(world)
    _pending(world, "holding-units", 10.0, 20.0, 110.0)
    view = _view(world, 130.0)
    assert view.terminal_state == TERMINAL_WORK_PENDING
    assert view.unknown_count
    assert "unavailable" in view.summary_line()
    assert "needs attention" in view.summary_line() or "need attention" in view.summary_line()


def test_safe_33_08_proposal_without_a_declared_stream_is_not_rendered(world):
    _register_holding(world)
    proposal = _pending(world, "holding-units", 10.0, 20.0, 110.0)
    world["streams"].streams.pop("holding-units")
    view = _view(world, 130.0)
    assert all(item.proposal_id != proposal.id for item in view.items)
    assert all(item.subject_id != "holding-units" for item in view.items)
