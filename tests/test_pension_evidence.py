"""RFC-009 pension evidence envelope and replay semantics."""

import pytest

from foundry.eventlog import EventLog
from foundry.finance.pension_evidence import (
    EVENT_KIND,
    PensionEvidenceProjection,
    record_pension_evidence,
)


def _record(log, field, value, effective_at=100.0, **overrides):
    units = {
        "employee_contribution_annual": "GBP",
        "employer_contribution_annual": "GBP",
        "salary_sacrifice_annual": "GBP",
        "contribution_payment_employee": "GBP",
        "contribution_payment_employer": "GBP",
        "annual_fee_percent": "fraction",
        "db_annual_income_accrued": "GBP",
        "db_normal_pension_age": "years",
        "state_pension_annual": "GBP",
        "state_pension_age": "years",
        "state_pension_basis": None,
    }
    return record_pension_evidence(
        log,
        overrides.pop("subject_id", "pension-1"),
        field,
        value,
        effective_at,
        confidence=overrides.pop("confidence", .9),
        source=overrides.pop("source", "scheme statement"),
        lineage=overrides.pop("lineage", "statement supplied by household"),
        unit_or_currency=overrides.pop(
            "unit_or_currency", units[field]),
        **overrides,
    )


def test_rates_supersede_while_dated_payments_accumulate(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    older = _record(log, "employee_contribution_annual", 4_000.0, 100.0)
    newer = _record(log, "employee_contribution_annual", 5_000.0, 200.0)
    first_payment = _record(
        log, "contribution_payment_employee", 400.0, 150.0)
    second_payment = _record(
        log, "contribution_payment_employee", 450.0, 200.0)

    evidence = PensionEvidenceProjection(log)

    assert evidence.latest(
        "pension-1", "employee_contribution_annual", 250.0) == newer
    assert older in evidence.for_subject("pension-1", 250.0)
    assert evidence.payments("pension-1", 250.0) == (
        first_payment, second_payment)


def test_equal_time_supersession_uses_append_order_not_uuid(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    _record(log, "annual_fee_percent", .008, 100.0)
    latest = _record(log, "annual_fee_percent", .006, 100.0)

    assert PensionEvidenceProjection(log).latest(
        "pension-1", "annual_fee_percent", 100.0) == latest


@pytest.mark.parametrize(
    "field,value,unit,message",
    [
        ("unknown", 1.0, "GBP", "unsupported"),
        ("employee_contribution_annual", -1.0, "GBP", "non-negative"),
        ("employee_contribution_annual", 1.0, "USD", "GBP"),
        ("annual_fee_percent", 1.1, "fraction", "fraction"),
        ("state_pension_age", 150.0, "years", "age"),
        ("state_pension_basis", "guessed", None, "unsupported"),
    ],
)
def test_writer_rejects_invalid_envelopes_before_append(
        tmp_path, field, value, unit, message):
    log = EventLog(tmp_path / "events.jsonl")
    before = len(list(log.events()))

    with pytest.raises((KeyError, ValueError), match=message):
        if field == "unknown":
            record_pension_evidence(
                log, "pension-1", field, value, 100.0,
                confidence=.9, source="source", lineage="lineage",
                unit_or_currency=unit)
        else:
            _record(
                log, field, value, unit_or_currency=unit)

    assert len(list(log.events())) == before


def test_malformed_direct_log_envelope_is_quarantined_not_dropped(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    valid = _record(log, "employer_contribution_annual", 3_000.0)
    hostile = log.append(EVENT_KIND, {
        "subject_id": "pension-1",
        "field": "employer_contribution_annual",
        "value": "<script>alert(1)</script>",
        "effective_at": 100.0,
        "confidence": .9,
        "source": "hostile",
        "lineage": [],
        "unit_or_currency": "GBP",
    })

    evidence = PensionEvidenceProjection(log)

    assert evidence.latest(
        "pension-1", "employer_contribution_annual", 200.0) == valid
    assert hostile["id"] in evidence.invalid_event_ids
    assert evidence.has_invalid_for({"pension-1"}, 200.0)


def test_future_evidence_is_excluded_and_remains_visible(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    current = _record(log, "state_pension_annual", 10_600.0, 100.0,
                      subject_id="member-1")
    future = _record(log, "state_pension_annual", 11_000.0, 300.0,
                     subject_id="member-1")
    evidence = PensionEvidenceProjection(log)

    assert evidence.latest(
        "member-1", "state_pension_annual", 200.0) == current
    assert evidence.future_for("member-1", 200.0) == (future,)
