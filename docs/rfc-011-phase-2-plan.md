# RFC-011 Phase 2 Plan — After Governor Phase 1 Approval

## Objective

Harden the manual/evidence operation around the now-proven seam without
opening another acquisition channel.

## Planned work

First, replace the Phase 1 vault deployment assumption with a reviewed
encryption/key-management adapter and explicit per-artefact Governor
redaction approval. Preserve the content-addressed API, hash commitment,
authorization check and redaction event exactly.

Second, add the governed correction/reconciliation workflow: a reviewer can
link a duplicate or replacement to prior confirmed evidence without mutating
historical proposals or canonical events.

Third, expose domain-owned accessibility profile and condition-transition
proposals in the same authenticated inbox, retaining the rule that Core owns
only lifecycle shape and Finance asserts real-world satisfaction.

Fourth, run the manual reference workflow against approved real child-account
evidence held only in the vault. No raw data, account identifiers, or evidence
payload enters the repository, fixture set or logs.

## Exit criteria

The Governor sees a walkthrough from protected evidence to confirmed canonical
events, a redaction authorization trail, a corrected/reconciled observation,
replay parity, cross-household refusal and unchanged adult mission results.

## Explicit exclusions

Phase 2 still excludes PayPal RSUs, APIs, email/PDF, CSV, OCR, Open Banking,
cash/bank accounts, bills, precious metals and private/director equity. Those
require their own approved burns after the Governor gate.
