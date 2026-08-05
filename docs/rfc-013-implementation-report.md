# RFC-013 — Operations Capture Contracts: Implementation Report

**Status:** implemented; ready for SAFE review.  **Scope:** metadata and
orchestration only.  This report records the implementation of the approved
Capture Contract Registry described in the RFC-013 mission brief.

## Delivered boundary

`foundry.capture_contracts` owns versioned, declarative `CaptureContract`
metadata: identifier, version, display name, description, capabilities,
renderer-neutral schema, validation, review template, evidence policy and
canonical mapper.  `CaptureContractRegistry` discovers registered contracts;
Operations only queries it.  An injected registry can add a fourth contract
without a route or renderer change.

The initial production registrations are Pension Balance Update, Cash Balance
Update and Property Valuation Update.  Their mappers produce only inert
RFC-011 manual facts.  Pension and property values map to the pre-existing
`finance.valuation.declared` canonical shape; cash maps to the pre-existing
`finance.account.reconciliation_observed` shape.  Finance's existing draft
contract now admits the former, with its existing required payload shape.
No canonical event definition changed.

## Operations flow

`GET /operations/capture` asks “What do you want to record?” and renders the
registry's contracts.  The generic contract form filters to declared manual
streams that the selected contract has declared compatible.  It never accepts
a user-supplied event kind, event payload, observation kind or subject id.

On submission, Operations validates the selected contract, stores the
contract identifier and version in immutable evidence, then invokes the
existing `ManualAcquisitionProvider` and `FinanceManualInterpreter`.  The
result is a pending acquisition proposal.  Confirmation remains exclusively
at RFC-011's existing CSRF-protected inbox gate.  No submission writes a
`finance.*` event directly.

Evidence policies are explicit values: `NONE`, `OPTIONAL`, `RECOMMENDED` and
`REQUIRED`.  The property valuation contract requires an evidence reference;
all captures still retain the immutable RFC-011 evidence envelope.

## Verification

`tests/test_rfc_013_capture_contracts.py` proves production discovery,
metadata completeness, fourth-contract registration, required evidence,
declarative mapping, authenticated generic rendering, proposal creation and
subsequent confirmation.  It also asserts no canonical Finance event exists
before confirmation.

The focused compatibility suite passed:

```text
19 passed
tests/test_rfc_013_capture_contracts.py
tests/test_rfc_012_operations_web.py
tests/test_rfc_011_acquisition.py
```

The full suite also passed: `654 passed`.

## Architectural non-changes

RFC-011 provider, interpreter, evidence vault, proposal lifecycle,
confirmation gate and provenance chain are retained.  RFC-012's Operations
Console model is untouched.  No Core or Finance event type, Canon path,
event-sourcing behaviour, approval policy or SAFE-012-01 authentication/CSRF
control is bypassed or weakened.
