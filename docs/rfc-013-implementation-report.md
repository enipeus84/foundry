# RFC-013 — Operations Capture Contracts: Implementation Report

**Status:** proposed Capture Contracts change; SAFE returned **GO WITH
FINDINGS** and the mandatory remediation has been performed.  **Scope:**
metadata and orchestration only.  RFC-number and architecture reconciliation
remain a Governor decision before merge; this report claims neither a resolved
RFC number nor architectural approval.

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

### Cash Balance Update product boundary

Cash Balance Update is intentionally **record-only for Finance projections**.
Its confirmed event is a canonical stated account observation; it does not
update the Finance transaction ledger, account balance, net worth, liquidity,
or any other downstream Finance projection.  The current RFC-011
reconciliation lens consumes `statement_total` observations, not this
contract's `cash_balance` observation, so Cash Balance Update is not currently
a reconciliation input either.  Finance values accounts from their transaction
ledger and contained positions.  Changing that rule would alter the established
Finance model, so this contract describes the boundary explicitly rather than
implying a projection effect it does not have.

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

Evidence-reference policies are explicit values: `NONE`, `OPTIONAL`,
`RECOMMENDED` and `REQUIRED`.  The property valuation contract requires an
evidence reference; the UI distinguishes a recommended reference from an
optional one.  Foundry stores the capture payload and reference string in the
immutable RFC-011 evidence envelope.  It does not upload, verify or claim
custody of the externally referenced artefact; manual capture remains at the
existing `declared` evidence grade.

## SAFE remediation

F1 is resolved: a valuation draft identifier is derived from the contract
identifier/version, stream, subject and normalised capture values (including
the evidence reference).  Identical submissions therefore generate byte-
identical evidence, reusing RFC-011's existing envelope and proposal
idempotency.  Changes to amount, effective time or evidence reference create
a distinct proposal, as documented policy.

F2 is resolved: Operations form attributes are constructed without an escaped
quote inside an f-string expression, preserving Python 3.10 parsing.

F3 is hardened: capture `valid_at` is constrained to the Unix range from epoch
through 9999-12-31, and inbox timestamp rendering safely reports invalid
stored values.  F4 is hardened: a contract must declare at least one compatible
stream property.  F5 is documented and made visible in the generic capture
surface; it does not create an evidence-upload or custody subsystem.

## Verification

`tests/test_rfc_013_capture_contracts.py` proves production discovery,
metadata completeness, fourth-contract registration, required evidence,
declarative mapping, authenticated generic rendering, proposal creation and
subsequent confirmation.  It also asserts no canonical Finance event exists
before confirmation.

The focused RFC-013/acquisition/Operations suite passed:

```text
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest \
  tests/test_rfc_013_capture_contracts.py \
  tests/test_rfc_012_operations_web.py \
  tests/test_rfc_011_acquisition.py -q -p no:cacheprovider

26 passed
```

The final full suite passed:

```text
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest tests -q -p no:cacheprovider

661 passed
```

## Architectural non-changes

RFC-011 provider, interpreter, evidence vault, proposal lifecycle,
confirmation gate and provenance chain are retained.  RFC-012's Operations
Console model is untouched.  No Core or Finance event type, Canon path,
event-sourcing behaviour, approval policy or SAFE-012-01 authentication/CSRF
control is bypassed or weakened.
