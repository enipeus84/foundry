"""RFC-008 manual resilience evidence contract."""

import pytest

from foundry.eventlog import EventLog
from foundry.finance.resilience_evidence import (
    ResilienceEvidenceProjection,
    record_resilience_evidence,
)


def _record(
    log,
    *,
    field="essential_outflow_monthly",
    value=2_000.0,
    effective_at=100.0,
    confidence=.9,
    due_at=None,
    description="",
    source="manual household declaration",
):
    return record_resilience_evidence(
        log,
        "household-1",
        field,
        value,
        effective_at,
        confidence=confidence,
        source=source,
        lineage="attributed source record",
        unit_or_currency=(
            "GBP" if field != "protection_declaration" else None),
        due_at=due_at,
        description=description,
    )


def test_evidence_preserves_scope_provenance_lineage_and_due_date(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    recorded = _record(
        log,
        field="near_term_commitment",
        value=4_000.0,
        due_at=180.0,
        description="annual tax payment",
    )

    replayed = ResilienceEvidenceProjection(log).latest(
        "household-1", "near_term_commitment", 150.0)

    assert replayed == recorded
    assert replayed.due_at == 180.0
    assert replayed.confidence == .9
    assert replayed.source == "manual household declaration"
    assert replayed.lineage == "attributed source record"
    assert replayed.description == "annual tax payment"
    assert replayed.event_id


def test_projection_is_as_of_filtered_scope_isolated_and_deterministic(
        tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    older = _record(log, value=2_000.0, effective_at=100.0)
    newer = _record(log, value=2_100.0, effective_at=200.0)
    record_resilience_evidence(
        log,
        "household-2",
        "essential_outflow_monthly",
        99_000.0,
        100.0,
        confidence=.9,
        source="other household",
        lineage="isolated",
        unit_or_currency="GBP",
    )

    projection = ResilienceEvidenceProjection(log)
    assert projection.latest(
        "household-1", "essential_outflow_monthly", 150.0) == older
    assert projection.latest(
        "household-1", "essential_outflow_monthly", 250.0) == newer
    assert projection.for_party(
        "household-1", 250.0) == (older, newer)
    assert projection.for_party(
        "household-1", 250.0) == projection.for_party(
            "household-1", 250.0)


def test_equal_effective_dates_use_append_order_not_uuid(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    _record(log, value=2_000.0)
    latest = _record(log, value=2_100.0)

    assert ResilienceEvidenceProjection(log).latest(
        "household-1", "essential_outflow_monthly", 100.0) == latest


def test_latest_by_source_supersedes_corrections_without_inference(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    first = _record(
        log,
        field="income_source_monthly",
        value=4_000.0,
        source="payroll feed A",
    )
    other = _record(
        log,
        field="income_source_monthly",
        value=1_000.0,
        source="pension statement B",
    )
    corrected = _record(
        log,
        field="income_source_monthly",
        value=3_800.0,
        effective_at=110.0,
        source="payroll feed A",
    )

    current = ResilienceEvidenceProjection(log).latest_by_source(
        "household-1", "income_source_monthly", 120.0)

    assert current == (other, corrected)
    assert first not in current


@pytest.mark.parametrize("changes,match", [
    ({"field": "invented"}, "unsupported"),
    ({"value": float("nan")}, "finite"),
    ({"effective_at": float("inf")}, "finite"),
    ({"confidence": 1.1}, "between zero and one"),
    ({"source": ""}, "must not be empty"),
    ({"lineage": ""}, "must not be empty"),
    (
        {"field": "near_term_commitment", "value": 1_000.0},
        "requires due_at",
    ),
    (
        {"field": "income_source_monthly", "due_at": 200.0},
        "cannot carry due_at",
    ),
])
def test_invalid_manual_evidence_is_rejected_before_append(
        tmp_path, changes, match):
    log = EventLog(tmp_path / "events.jsonl")
    kwargs = {
        "field": "essential_outflow_monthly",
        "value": 2_000.0,
        "effective_at": 100.0,
        "confidence": .9,
        "source": "manual declaration",
        "lineage": "attributed source",
        "unit_or_currency": "GBP",
    }
    kwargs.update(changes)

    with pytest.raises(ValueError, match=match):
        record_resilience_evidence(log, "household-1", **kwargs)
    assert tuple(log.events()) == ()


def test_hostile_log_event_is_quarantined_without_hiding_valid_data(
        tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    valid = _record(log)
    hostile = log.append("finance.resilience_evidence.recorded", {
        "party_id": "household-1",
        "field": "__class__",
        "value": "<script>",
        "effective_at": 100.0,
        "confidence": "trusted",
        "source": {"forged": True},
        "lineage": [],
    })

    projection = ResilienceEvidenceProjection(log)

    assert projection.latest(
        "household-1", "essential_outflow_monthly", 200.0) == valid
    assert projection.invalid_event_ids == [hostile["id"]]
    assert projection.has_invalid_for("household-1", 200.0)


def test_unattributable_invalid_event_never_crosses_household_scope(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    hostile = log.append("finance.resilience_evidence.recorded", {
        "field": "__class__",
        "value": "<script>",
        "effective_at": 100.0,
        "confidence": "trusted",
        "source": {"forged": True},
        "lineage": [],
    })

    projection = ResilienceEvidenceProjection(log)

    assert projection.invalid_event_ids == [hostile["id"]]
    assert projection.invalid_records[0].party_id is None
    assert not projection.has_invalid_for("household-1", 200.0)
    assert not projection.has_invalid_for("household-2", 200.0)


def test_future_evidence_is_visible_but_excluded_from_current_values(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    future = _record(log, effective_at=300.0)
    projection = ResilienceEvidenceProjection(log)

    assert projection.for_party("household-1", 200.0) == ()
    assert projection.future_for("household-1", 200.0) == (future,)


def test_protection_field_is_reserved_text_and_not_a_scoring_vocabulary(
        tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    record = _record(
        log,
        field="protection_declaration",
        value="future source record only",
    )

    assert record.unit_or_currency is None
    assert record.value == "future source record only"
