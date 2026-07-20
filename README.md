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
pip install ".[web]"           # + FastAPI status/web layer
```

## Web interface

A minimal deployment shell over the substrate. The core package keeps
zero runtime dependencies; `foundry/__init__.py` never imports the web
layer, and a test enforces that.

Run locally:

```bash
pip install -e ".[web]"
uvicorn foundry.web:app --host 0.0.0.0 --port 8000
# http://localhost:8000/        Flight Deck — Mission Control home (requires session)
# http://localhost:8000/health  {"status": "ok", ...}
```

Deploy on Render (Blueprint — uses `render.yaml`):

1. Push this repository to GitHub.
2. In the Render dashboard: **New → Blueprint**, select the repo.
3. Render reads `render.yaml`: build `pip install -e ".[web]"`,
   start `uvicorn foundry.web:app --host 0.0.0.0 --port $PORT`,
   health check on `/health`. Accept and deploy.

Or as a plain Web Service (no blueprint): **New → Web Service**, select
the repo, set the build and start commands to the two lines above.

### Authentication

Mission Control requires Google sign-in via Supabase; `/health` stays
public for Render health checks. Sessions are stateless HMAC-signed
cookies (HttpOnly, SameSite=Lax, Secure when `APP_BASE_URL` is https).
The layer fails closed: without configuration, nobody gets in.

Environment variables (set in the Render dashboard, never in source):

```
SUPABASE_URL              https://<project>.supabase.co
SUPABASE_PUBLISHABLE_KEY  the project's publishable (anon) key
FOUNDRY_ALLOWED_EMAIL     the single permitted Google account
SESSION_SECRET            openssl rand -hex 32
APP_BASE_URL              the deployed URL, e.g. https://foundry.onrender.com
```

In Supabase: enable the Google provider (Authentication → Providers),
and add `<APP_BASE_URL>/auth/callback` to the allowed redirect URLs
(Authentication → URL Configuration).

### Demo mode

A temporary capability for evaluating Mission Control's UI on a real
deployment before any personal data exists (RFC-003.3) — **not** a
database, **not** real-data import, **not** persistent storage. It
reuses the exact synthetic Morgan household `examples/
seed_synthetic_household.py` seeds locally (`foundry.demo_data.build`),
run once at process startup instead of by hand.

```
FOUNDRY_DEMO_DATA=true
FOUNDRY_DATA_PATH=/tmp/foundry/events.jsonl
```

Set both in the Render dashboard (or your deployment's own env-var
config) to enable it. The value must be **exactly** `true` —
lowercase, unpadded; `TRUE`, `1`, `yes`, or anything else preserves
the current behaviour bit-for-bit (no file is even created at
startup), so a truthy-looking typo can never switch a deployment
into demo mode. **Never enable this on an environment meant to hold
real data** — only where wiping the dataset is always acceptable.

Behaviour, checked at every process start:

- `FOUNDRY_DEMO_DATA` is not exactly `true` → nothing happens,
  unchanged from before this capability existed.
- `FOUNDRY_DEMO_DATA=true` and the file at `FOUNDRY_DATA_PATH` is
  missing or zero-byte → seeded once with the synthetic household.
  The dataset is built in a same-directory temp file, hash-chain
  verified, then atomically renamed into place — the log is never
  observable half-written, a crash mid-seed leaves the target
  untouched, and a sibling `.lock` file serialises simultaneous
  starts (multi-worker deployments) so exactly one process seeds.
- `FOUNDRY_DEMO_DATA=true` and the file has *any* existing content —
  real events, a previous seed, even something malformed → left
  completely alone, byte-for-byte, logged as skipped (with a
  critical-level warning if the content doesn't verify as an event
  log — preserved as evidence, never "repaired"). There is no HTTP
  route that can trigger seeding — it only runs at startup,
  in-process.
- An unwritable `FOUNDRY_DATA_PATH`, or one that points at a
  directory, fails the process at startup (fail closed) rather than
  coming up silently without the data it was asked to seed.

Every seeded log permanently carries a first-class marker Claim
(actor `synthetic_demo`, statement beginning `SYNTHETIC DEMO DATA`)
so the file itself — greppable, replayable — can never be mistaken
for a real household later, whatever happens to this documentation.

**Render's default filesystem is ephemeral.** A path like
`/tmp/foundry/events.jsonl` (or anywhere outside a persistent disk)
does not survive a redeploy or restart — demo mode will simply
re-seed a fresh household next time the process starts, which is the
intended, disposable behaviour for UI evaluation. This capability
does not add a persistent disk or a database; if you need the
dataset to survive restarts, that's a separate piece of work, not
this one.

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
  demo_data.py    synthetic Morgan household builder + demo-mode
                  startup hook (FOUNDRY_DEMO_DATA) — not real data
  errors.py       three exceptions; each demands a different response
  cli.py          minimal CLI (`foundry ingest|derive|ask|why|verify`)
  core/           domain-agnostic layer every product domain depends on
                  (docs/specifications/000-core-domain-model.md):
                  Party/Employer/Mission, the Decision lifecycle, the
                  Core Evidence Index, the Metric Provider contract,
                  Flight Deck composition. No Finance, no other domain.
tests/            each test is an architectural claim
scripts/validate.py   validation harness & transcript generator
docs/             architecture, roadmap, historical assessments,
                  specifications (docs/specifications/)
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
