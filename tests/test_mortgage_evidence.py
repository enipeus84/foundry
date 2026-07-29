"""RFC-007 manual mortgage evidence contract."""

from datetime import datetime, timezone

import pytest

from foundry.demo_data import build
from foundry.eventlog import EventLog
from foundry.finance.entities import FinanceEntityProjection
from foundry.finance.mortgage_evidence import (
    MortgageEvidenceProjection,
    record_mortgage_evidence,
)


def _record(log, *, field="balance", value=242_540.09,
            effective_at=100.0, confidence=.9):
    return record_mortgage_evidence(
        log, "mortgage-1", field, value, effective_at,
        confidence=confidence, source="manual lender statement",
        lineage="NatWest statement supplied by household",
        unit_or_currency="GBP" if field == "balance" else None)


def test_manual_evidence_preserves_provenance_effective_date_and_lineage(
        tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    recorded = _record(log)
    replayed = MortgageEvidenceProjection(log).latest(
        "mortgage-1", "balance", 200.0)

    assert replayed == recorded
    assert replayed.effective_at == 100.0
    assert replayed.confidence == .9
    assert replayed.source == "manual lender statement"
    assert replayed.lineage == "NatWest statement supplied by household"
    assert replayed.event_id


def test_evidence_projection_is_as_of_filtered_and_deterministic(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    older = _record(log, value=250_000.0, effective_at=100.0)
    newer = _record(log, value=242_540.09, effective_at=200.0)

    assert MortgageEvidenceProjection(log).latest(
        "mortgage-1", "balance", 150.0) == older
    first = MortgageEvidenceProjection(log).for_obligation("mortgage-1", 250.0)
    second = MortgageEvidenceProjection(log).for_obligation("mortgage-1", 250.0)
    assert first == second == (older, newer)


def test_equal_effective_dates_use_append_order_not_random_event_id(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    _record(log, value=250_000.0, effective_at=100.0)
    latest = _record(log, value=242_540.09, effective_at=100.0)

    assert MortgageEvidenceProjection(log).latest(
        "mortgage-1", "balance", 100.0) == latest


@pytest.mark.parametrize("changes,match", [
    ({"field": "invented"}, "unsupported"),
    ({"value": float("nan")}, "finite"),
    ({"effective_at": float("inf")}, "finite"),
    ({"confidence": 1.1}, "between zero and one"),
    ({"source": ""}, "non-empty"),
    ({"lineage": ""}, "non-empty"),
    ({"field": "original_term_months", "value": 300.5}, "whole number"),
])
def test_invalid_manual_evidence_is_rejected_before_append(
        tmp_path, changes, match):
    log = EventLog(tmp_path / "events.jsonl")
    kwargs = {
        "field": "balance", "value": 242_540.09,
        "effective_at": 100.0, "confidence": .9,
        "source": "manual lender statement",
        "lineage": "NatWest statement supplied by household",
    }
    kwargs.update(changes)

    with pytest.raises(ValueError, match=match):
        record_mortgage_evidence(log, "mortgage-1", **kwargs)
    assert tuple(log.events()) == ()


def test_hostile_log_event_isolated_without_breaking_valid_evidence(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    valid = _record(log)
    hostile = log.append("finance.mortgage_evidence.recorded", {
        "obligation_id": "mortgage-1",
        "field": "__class__",
        "value": "<script>",
        "effective_at": 100.0,
        "confidence": "trusted",
        "source": {"forged": True},
        "lineage": [],
    })

    projection = MortgageEvidenceProjection(log)

    assert projection.latest("mortgage-1", "balance", 200.0) == valid
    assert projection.invalid_event_ids == [hostile["id"]]


def test_projection_does_not_reflect_unknown_payload_fields(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    valid = _record(log)
    event = next(log.events())
    event["payload"]["html"] = "<script>alert(1)</script>"
    # A forged in-memory envelope cannot create an attribute or alter replay.
    projection = MortgageEvidenceProjection.__new__(MortgageEvidenceProjection)
    projection.records, projection.invalid_event_ids = {}, []
    projection.invalid_records = []
    projection.apply(event)

    replayed = projection.latest("mortgage-1", "balance", 200.0)
    assert replayed == valid
    assert not hasattr(replayed, "html")


def test_synthetic_demo_records_every_approved_mortgage_value(tmp_path):
    as_of = 1_785_170_000.0
    log = EventLog(tmp_path / "events.jsonl")
    household = build(log, as_of=as_of)
    finance = FinanceEntityProjection(log)
    mortgage = finance.obligations[household.mortgage_id]
    evidence = MortgageEvidenceProjection(log)

    expected = {
        "property_role": "primary_residence",
        "purchase_price": 450_000.0,
        "purchase_date": datetime(
            2025, 5, 1, tzinfo=timezone.utc).timestamp(),
        "property_valuation": 436_638.42,
        "lender": "NatWest",
        "original_advance": 310_000.0,
        "mortgage_start": datetime(
            2025, 7, 1, tzinfo=timezone.utc).timestamp(),
        "balance": 242_540.09,
        "repayment_type": "capital_repayment",
        "interest_type": "fixed",
        "interest_rate": .0433,
        "monthly_payment": 1_701.47,
        "payment_day": 1.0,
        "original_term_months": 300.0,
        "remaining_term_months": 201.0,
        "fixed_rate_expiry": datetime(
            2027, 7, 31, tzinfo=timezone.utc).timestamp(),
        "reported_ltv": .56,
    }

    assert mortgage.amount == 242_540.09
    for field, value in expected.items():
        record = evidence.latest(mortgage.id, field, as_of)
        assert record is not None
        assert record.value == value
        assert record.source
        assert record.lineage
        assert record.confidence == .9
    purchase = evidence.latest(mortgage.id, "purchase_price", as_of)
    valuation = evidence.latest(mortgage.id, "property_valuation", as_of)
    assert purchase is not None
    assert valuation is not None
    assert purchase.effective_at == datetime(
        2025, 5, 1, tzinfo=timezone.utc).timestamp()
    assert valuation.effective_at == datetime(
        2025, 3, 31, tzinfo=timezone.utc).timestamp()
    assert valuation.source == "HPI"
    assert "dated valuation reference" in valuation.lineage
    overpayments = tuple(
        record.value for record in evidence.for_obligation(
            mortgage.id, as_of)
        if record.field == "recorded_overpayment")
    assert overpayments == (30_000.0, 30_000.0)
