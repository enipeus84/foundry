# Foundry Prototype Alpha — Architecture & Honest Assessment

## Architecture

```
                        ┌─────────────────────────┐
                        │      Model Adapters      │   replaceable
                        │  alpha │ beta │ claude │ gpt   "CPUs"
                        └───────────┬─────────────┘
                                    │ one interface:
                                    │ extract_claims / answer / name
                        ┌───────────▼─────────────┐
                        │        KERNEL            │   7 syscalls:
                        │  ingest · derive ·       │   stateless
                        │  retrieve · ask ·        │   orchestration
                        │  update · link · resolve │
                        └─────┬──────────────┬─────┘
                              │ append only  │ replay
                    ┌─────────▼────────┐ ┌───▼──────────────┐
                    │    EVENT LOG      │ │      CANON        │
                    │ immutable JSONL,  │ │ derived claims =  │
                    │ hash-chained.     │ │ pure projection.  │
                    │ THE ONLY TRUTH.   │→│ deletable,        │
                    │                   │ │ rebuildable.      │
                    └───────────────────┘ └──────────────────┘
```

**The single most important line in the codebase** is that the Canon has
no write path of its own. `claim.derived`, `claim.updated`,
`claim.superseded`, `claim.linked` are all *events*. The Canon is
`rebuild()` — a fold over the log. This is what makes memory "derived
state over immutable events" true rather than aspirational.

## Design decisions

1. **Claim mutations are events.** The brief contained a latent
   contradiction: "claims may evolve, events never do" plus "every
   answer must be traceable." If claims mutate in place, the evolution
   is untraceable — you can answer *why do you believe this* but not
   *why did you stop believing that*. Event-sourcing the claims
   resolves it and collapses the design to one storage primitive.

2. **Model identity is part of provenance, not hidden by the
   abstraction.** Every derivation event records `actor: <model name>`.
   See the honest assessment below for why this is forced.

3. **JSONL over a database.** Greppable, diffable, durable, and honest
   about scale ambitions (none, per the brief).

4. **Hash chaining.** Immutability declared in a docstring is a wish;
   immutability verifiable by `log.verify()` is a property. ~10 lines.

5. **Deliberately dumb retrieval** (word overlap). Retrieval quality is
   not the thesis under test; replaceability is. An embedding index is
   just another projection — rebuildable from the log, so adding one
   later breaks nothing.

6. **Two divergent mock models** rather than one. The swap must be
   *visible* to be a demonstration. Alpha and Beta extract different
   claims at different confidences; the substrate absorbs both.

## Honest assessment of the central claim

**"Models are CPUs. Foundry is the OS and filesystem."**

The claim is **half true, and the true half is valuable.**

**True:** state independence. The event log + canon survive a model
swap with zero migration. A claim derived by model A is retrieved,
cited, superseded and explained identically under model B. Test
`test_6_and_7` and demo steps 7–8 prove this mechanically. The
filesystem half of the analogy holds completely.

**False:** the CPU half. CPUs share an instruction set; two x86 chips
given the same program produce the same output. Two LLMs given the same
text extract *different claims at different confidences* — the demo
shows Alpha and Beta diverging on identical input. A model is not an
interchangeable executor; it is a **witness with an identity**. The
architecture survives only because provenance records which model
asserted what. Corollary: a Canon built entirely by model A is not
"neutral state" — it is A's reading of the events. The events are
model-neutral; the claims never are.

**The correct analogy** is not OS/CPU. It is **court record and
witnesses**: the event log is the exhibit locker (immutable), claims
are testimony (attributed, contestable, supersedable), the kernel is
procedure. That framing predicts the system's real behaviours —
conflict resolution, confidence, supersession — where the CPU framing
predicts none of them.

**Second finding:** the architecture is event sourcing + CQRS with an
LLM as the projection function. That is *good* news — the substrate
pattern has 15 years of production hardening behind it. The novel part,
and the only genuinely hard part, is the projection function being
stochastic and paid-per-call.

## Risks and limitations

- **Confidence numbers are theatre.** LLM-reported confidences are not
  calibrated probabilities. Stored, displayed, never trusted for
  arithmetic. Real calibration needs cross-model agreement or human
  confirmation events.
- **Re-derivation cost.** "Canon is rebuildable" is cheap for replaying
  claim events; *re-deriving* claims from raw events through a model
  costs tokens and produces different output each run. Rebuild ≠
  re-derive; the design depends on the former.
- **Retrieval won't scale** past a few thousand events. Known,
  intentional, fixable as a projection.
- **No claim deduplication.** Two models asserting the same fact
  produce two claims. Needs an `identity` link relation or a merge
  kernel op.
- **Conflict *detection* is manual.** Resolution exists;
  noticing that two claims conflict currently requires a human or a
  model pass that doesn't exist yet.

## Suggested next iteration

1. Conflict detection as a kernel op (model compares claim pairs,
   emits `claim.conflict` events for human/policy resolution).
2. Embedding index as a second projection — proves "projections are
   cheap and disposable" a second time.
3. Cross-model corroboration: same event derived by two models,
   agreement raises confidence via `claim.updated` events. This turns
   the model-divergence weakness into the calibration mechanism.
4. Snapshot/compaction strategy for when replay gets slow (standard
   event-sourcing playbook applies directly).

## Verdict

The architecture survives contact with reality **after one amendment it
could not survive without**: model identity promoted from hidden
substrate detail to first-class provenance. Amended, the thesis holds —
durable, model-independent, fully traceable memory is demonstrably
buildable in ~600 lines. Proceed.
