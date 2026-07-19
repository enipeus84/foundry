"""Integration tests for the synthetic Morgan household seed script
(RFC-003.2, examples/seed_synthetic_household.py) — proving the dataset
it produces is a legitimate exercise of the whole pipeline, not a
shortcut around it: real writes through Core/Finance's own functions,
real replay, every Mission Control KPI actually available, and nothing
that varies between two independent rebuilds of the same log."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import webauth  # noqa: E402
from foundry.core.entities import EntityProjection  # noqa: E402
from foundry.core.evidence import EvidenceIndex  # noqa: E402
from foundry.core.metrics import MetricRegistry, MetricRequest  # noqa: E402
from foundry.core.mission_evaluation import get_mission_status  # noqa: E402
from foundry.core.scope import Subject  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.finance.entities import FinanceEntityProjection  # noqa: E402
from foundry.finance.metrics import FinanceMetricProvider  # noqa: E402
from foundry.web import app  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
import seed_synthetic_household as seed  # noqa: E402

ALLOWED = "cparkerbrads@gmail.com"

KPI_METRIC_IDS = (
    "finance.net_worth", "finance.liquidity_runway",
    "finance.employer_concentration", "finance.debt_ratio", "finance.cash_available",
)


def _as_of(log: EventLog) -> float:
    last = 0.0
    for e in log.events():
        last = e["ts"]
    return last


def _console_pieces(log: EventLog):
    core_entities = EntityProjection(log)
    finance_entities = FinanceEntityProjection(log)
    registry = MetricRegistry()
    registry.register(FinanceMetricProvider(finance_entities, core_entities))
    return core_entities, finance_entities, registry


@pytest.fixture
def household_log(tmp_path) -> EventLog:
    log = EventLog(tmp_path / "events.jsonl")
    seed.build(log)
    return log


# ------------------------------------------------------------------ dataset

def test_dataset_writes_only_core_finance_and_claim_event_kinds(household_log):
    """No `ingest` events, no stray domains — this is a Core/Finance
    dataset built entirely through the Event Log's own writers."""
    kinds = {e["kind"].split(".")[0] for e in household_log.events()}
    assert kinds <= {"core", "finance", "claim"}


def test_dataset_spans_roughly_twenty_four_months(household_log):
    timestamps = [e["payload"]["ts"] for e in household_log.events()
                  if e["kind"] == "finance.transaction.declared"]
    span_months = (max(timestamps) - min(timestamps)) / (30 * 24 * 3600.0)
    assert 22.0 <= span_months <= 24.5


def test_household_has_four_members_two_owning_the_core_accounts(household_log):
    core_entities = EntityProjection(household_log)
    households = [p for p in core_entities.parties.values() if p.party_type == "household"]
    assert len(households) == 1
    members = core_entities.members_of(households[0].id)
    assert len(members) == 4


def test_full_mission_lifecycle_is_present(household_log):
    """Mission -> Decision -> Execution -> Outcome -> Review -> Learning
    (000 §12), each stage actually represented in the log, not merely
    implied by the script's structure."""
    kinds = [e["kind"] for e in household_log.events()]
    assert "core.mission.declared" in kinds
    assert "core.decision.declared" in kinds
    assert "core.decision_outcome.declared" in kinds
    # Execution: a domain event linked `executes` back to the Decision.
    executions = [e for e in household_log.events()
                  if e["kind"] == "finance.position.linked"
                  and e["payload"].get("relation") == "executes"]
    assert len(executions) == 1
    # Review + Learning: Claims tagged accordingly.
    review_tags = [e for e in household_log.events()
                   if e["kind"] == "claim.tagged" and e["payload"].get("value") == "review"]
    recommendation_tags = [e for e in household_log.events()
                            if e["kind"] == "claim.tagged"
                            and e["payload"].get("tag_type") == "insight_type"
                            and e["payload"].get("value") == "recommendation"]
    assert review_tags
    assert recommendation_tags  # the Learning claim (and the seeded next-decision claim)


# -------------------------------------------------------------- replay/KPIs

def test_every_kpi_metric_is_available_for_the_household(household_log):
    core_entities, _finance_entities, registry = _console_pieces(household_log)
    as_of = _as_of(household_log)
    households = [p for p in core_entities.parties.values() if p.party_type == "household"]
    scope = Subject("party", households[0].id)

    for metric_id in KPI_METRIC_IDS:
        result = registry.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))
        assert result.status == "available", (metric_id, result.limitations)
        assert result.value is not None


def test_no_unsupported_metric_appears_for_the_household_scope(household_log):
    """Distinguishes this dataset from an incomplete one: every KPI the
    console renders resolves to a real number, never UNSUPPORTED."""
    core_entities, _finance_entities, registry = _console_pieces(household_log)
    as_of = _as_of(household_log)
    households = [p for p in core_entities.parties.values() if p.party_type == "household"]
    scope = Subject("party", households[0].id)

    for metric_id in KPI_METRIC_IDS:
        result = registry.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))
        assert result.status != "unsupported"


def test_mission_status_is_evaluable(household_log):
    core_entities, _finance_entities, registry = _console_pieces(household_log)
    as_of = _as_of(household_log)
    households = [p for p in core_entities.parties.values() if p.party_type == "household"]
    scope = Subject("party", households[0].id)
    missions = [m for m in core_entities.missions.values() if m.status == "active"]
    assert len(missions) == 1

    rag, result = get_mission_status(missions[0].id, core_entities, registry, scope, as_of)
    assert rag is not None
    assert result.status in ("available", "stale")


def test_replay_is_deterministic_across_independent_projections(household_log):
    """Two independent rebuilds of every projection from the same log
    must agree exactly — the substrate's own correctness oracle,
    exercised against this dataset specifically."""
    core_a, finance_a = EntityProjection(household_log), FinanceEntityProjection(household_log)
    core_b, finance_b = EntityProjection(household_log), FinanceEntityProjection(household_log)
    evidence_a, evidence_b = EvidenceIndex(household_log), EvidenceIndex(household_log)

    assert {k: vars(v) for k, v in core_a.parties.items()} == {k: vars(v) for k, v in core_b.parties.items()}
    assert {k: vars(v) for k, v in core_a.missions.items()} == {k: vars(v) for k, v in core_b.missions.items()}
    assert {k: vars(v) for k, v in finance_a.accounts.items()} == {k: vars(v) for k, v in finance_b.accounts.items()}
    assert {k: vars(v) for k, v in finance_a.positions.items()} == {k: vars(v) for k, v in finance_b.positions.items()}
    assert {k: vars(v) for k, v in finance_a.transactions.items()} == \
           {k: vars(v) for k, v in finance_b.transactions.items()}
    assert evidence_a.tags == evidence_b.tags
    assert evidence_a.subjects == evidence_b.subjects


def test_repeated_kpi_dispatch_gives_identical_results(household_log):
    """No difference between repeated rebuilds: dispatching the same
    metric twice, through two freshly built registries, agrees exactly."""
    core_a, _finance_a, registry_a = _console_pieces(household_log)
    core_b, _finance_b, registry_b = _console_pieces(household_log)
    as_of = _as_of(household_log)
    households = [p for p in core_a.parties.values() if p.party_type == "household"]
    scope = Subject("party", households[0].id)

    for metric_id in KPI_METRIC_IDS:
        result_a = registry_a.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))
        result_b = registry_b.dispatch(MetricRequest(metric_id=metric_id, scope=scope, as_of=as_of))
        assert result_a.value == result_b.value
        assert result_a.status == result_b.status


def test_verify_hash_chain_holds(household_log):
    assert household_log.verify()


# ------------------------------------------------------------- Mission Control

@pytest.fixture(autouse=True)
def auth_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(tmp_path / "events.jsonl"))
    yield


def _client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(ALLOWED, webauth.load_config()))
    return c


def test_mission_control_renders_the_seeded_dataset_with_no_unsupported_cards(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    seed.build(log)
    r = _client().get("/")
    assert r.status_code == 200
    assert "Coast FIRE by 2038" in r.text
    assert "UNSUPPORTED" not in r.text
    assert r.text.count("£") >= 2  # net worth + cash available, at minimum


def test_mission_control_drill_down_shows_lineage_for_every_kpi(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    seed.build(log)
    c = _client()
    for metric_id in KPI_METRIC_IDS:
        r = c.get(f"/metrics/{metric_id}")
        assert r.status_code == 200
        assert "UNSUPPORTED" not in r.text
        assert "input_references" in r.text


def test_mission_control_page_renders_deterministically(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    seed.build(log)
    c = _client()
    assert c.get("/").text == c.get("/").text


# ------------------------------------------------------------------ CLI

def test_seed_script_runs_as_a_subprocess_and_refuses_to_double_seed(tmp_path):
    """The actual deliverable: `python examples/seed_synthetic_household.py`
    against a fresh FOUNDRY_DATA_PATH succeeds, and running it again
    against the same path refuses rather than corrupting the log."""
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "examples" / "seed_synthetic_household.py"
    data_path = tmp_path / "events.jsonl"
    env = dict(os.environ)
    env["FOUNDRY_DATA_PATH"] = str(data_path)
    # Not `env["PYTHONPATH"] = str(repo_root / "src")`: PYTHONPATH is
    # `os.pathsep`-delimited (`:` on POSIX), and this checkout's own
    # directory name happens to contain literal colons — appended
    # there, it would be silently split into several bogus path
    # entries instead of the one real one. `-P`-safe regardless of
    # path contents: prepend to `sys.path` from inside the interpreter.
    runner = (f"import sys; sys.path.insert(0, {str(repo_root / 'src')!r}); "
              f"import runpy; runpy.run_path({str(script)!r}, run_name='__main__')")

    first = subprocess.run([sys.executable, "-c", runner], cwd=repo_root, env=env,
                            capture_output=True, text=True, timeout=120)
    assert first.returncode == 0, first.stderr
    assert data_path.exists()
    event_count = sum(1 for _ in EventLog(data_path).events())
    assert event_count > 0

    second = subprocess.run([sys.executable, "-c", runner], cwd=repo_root, env=env,
                             capture_output=True, text=True, timeout=120)
    assert second.returncode != 0
    assert "already has events" in second.stderr

    # Refusing to double-seed must not have touched the log.
    assert sum(1 for _ in EventLog(data_path).events()) == event_count
