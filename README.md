# Foundry

**Durable, model-independent, fully provenanced memory over an
immutable event log.**

Foundry demonstrates that organisational knowledge can outlive any
individual AI model. Source material enters an append-only, hash-chained
event log and is preserved verbatim forever. Models extract structured
claims from those events; every claim records its source event, its
verbatim evidence, and the identity of the model that asserted it.
Swap the model — mid-session, cross-vendor — and every claim, citation
and explanation keeps working, because state belongs to the substrate,
not the model.

Core is **pure standard library**. Zero runtime dependencies, by design:
the substrate must outlive the dependency ecosystem around it.

## Verify it works (under five minutes)

```bash
git clone <repo> && cd foundry
./validate.sh                              # architecture exercise (mocks)
ANTHROPIC_API_KEY=... ./validate.sh        # real-model validation
./validate.sh mynotes.md conversations.json  # over your own documents
```

One command creates a venv, installs, runs 34 tests, executes the full
validation workflow, and writes `v1_transcript.md` demonstrating
immutable events, provenance, claim extraction, cross-model
compatibility and deterministic replay.

## Install

```bash
pip install .                  # core, stdlib only
pip install ".[models]"        # + Anthropic and OpenAI adapters
pip install ".[dev]"           # + pytest
```

## Sixty-second tour

```python
from foundry import EventLog, Kernel
from foundry.models import MockModelAlpha, MockModelBeta

k = Kernel(EventLog("data/events.jsonl"), MockModelAlpha())

e = k.ingest("Alice is the technical lead. The budget is 75000 pounds.")
claims = k.derive(e["id"])          # model extracts attributed claims

k.why(claims[0].id)                 # full provenance: source event,
                                    # evidence, model identity, history

k.swap_model(MockModelBeta())       # the entire cost of changing models
k.ask("Who is the technical lead?") # old claims, new model, citations intact
```

Real models are one line: `AnthropicAdapter(key)` or
`OpenAIAdapter(key)` in place of a mock.

## Repository structure

```
src/foundry/
  eventlog.py     append-only hash-chained log — the only truth
  canon.py        claims as a pure, deterministic projection
  kernel.py       seven operations: ingest derive retrieve ask
                  update link resolve
  models.py       model adapters (two mocks, Anthropic, OpenAI)
  ingestors.py    real documents & conversation exports -> events
  errors.py       three exceptions; each demands a different response
  cli.py          minimal CLI (`foundry ingest|derive|ask|why|verify`)
tests/            34 tests; each is an architectural claim
scripts/validate.py   validation harness & transcript generator
docs/             architecture, roadmap, historical assessments
examples/         copy-paste-ready usage
```

## Documentation

- [Architecture](docs/architecture.md) — the thesis, the layers, the
  constitutional invariants, the known limitations
- [Roadmap](docs/roadmap.md) — everything deliberately not built yet
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Philosophy

Prefer simple code over clever code. The substrate is sacred; every
layer above it is replaceable. A model is a witness with an identity,
not an interchangeable executor. If a capability doesn't strengthen the
central demonstration, it goes on the roadmap, not in the code.

MIT licensed.
