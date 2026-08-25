"""Shared serialization for adapter-facing Mission reads.

These helpers only reshape canonical results for transport.  No assessment,
scope or completeness semantics live here.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from foundry.core.metrics import MetricResult


def iso(timestamp: float | None) -> str | None:
    """Render a canonical epoch timestamp as UTC ISO-8601."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def as_of_timestamp(value: str | None) -> float:
    """Parse a caller-supplied ISO-8601 ``as_of``; absent means now."""
    if value is None:
        return time.time()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("as_of must include a timezone")
    return parsed.timestamp()


def metric(result: MetricResult | None) -> dict[str, Any] | None:
    """Serialize one canonical metric result with its full provenance."""
    if result is None:
        return None
    return {
        "metric_id": result.metric_id,
        "value": result.value,
        "unit_or_currency": result.unit_or_currency,
        "status": result.status,
        "as_of": iso(result.as_of),
        "generated_at": iso(result.generated_at),
        "calculation_version": result.calculation_version,
        "input_references": list(result.input_references),
        "evidence_references": list(result.evidence_references),
        "assumption_references": list(result.assumption_references),
        "limitations": list(result.limitations),
    }
