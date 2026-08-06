# RFC-015 Phase 2A Amendment — Bootstrap Diagnostics

**Status:** proposed for Governor approval before fresh SAFE review.

## Narrow amendment

RFC-015 Phase 2 adds one canonical event kind:

```text
core.capture_target_bootstrap.diagnostic
```

It is owned by the RFC-015 Capture Target Registry boundary. The `core.`
namespace is correct because bootstrap is composition/infrastructure work and
the event records no Finance valuation, telemetry, or domain mutation.

## Payload and replay

Each event payload is exactly:

```json
{
  "household_id": "canonical household id or empty when discovery cannot identify one",
  "entity": "canonical entity id or stable bootstrap scope",
  "validation": "failed validation category",
  "reason": "non-sensitive failure reason"
}
```

The event is an immutable operational fact: a bootstrap run encountered a
canonical-state condition it could not safely interpret. It does not alter the
Capture Target projection, entity projection, or telemetry projection. On
replay, a consumer may reconstruct the observed diagnostics by selecting this
kind in log order; target eligibility remains derived solely from existing
asset-registration and telemetry declarations.

## Idempotency and rationale

Bootstrap appends the event only when the tuple `(household_id, entity,
validation, reason)` is absent from prior diagnostics. Repeated startup is
therefore silent for both registry declarations and unchanged diagnostics.

Without a canonical diagnostic, failure visibility exists only in process
memory and disappears across restart—the opposite of Foundry's append-only,
auditable operating model. This amendment authorises observation of a failed
bootstrap decision without creating a new capture-target aggregate, mutable
side store, or additional workflow.
