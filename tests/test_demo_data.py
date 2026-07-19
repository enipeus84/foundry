"""RFC-003.3 / RFC-003.3A — the FOUNDRY_DEMO_DATA startup hook.
Proves: disabled unless the value is exactly "true", idempotent,
atomic (a crash mid-seed leaves the target untouched), concurrency-
safe (two simultaneous starts produce exactly one dataset), never
touches existing content of any kind (real events, malformed bytes,
whitespace), fails closed on unwritable/directory paths, has no HTTP
route that can trigger it, permanently marks the dataset synthetic
in-band, and — once seeded — Mission Control actually renders the
synthetic household through it."""

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from foundry import demo_data  # noqa: E402
from foundry.demo_data import ensure_demo_data  # noqa: E402
from foundry import webauth  # noqa: E402
from foundry.eventlog import EventLog  # noqa: E402
from foundry.web import DEFAULT_DATA_PATH, _maybe_seed_demo_data, app  # noqa: E402

ALLOWED = "cparkerbrads@gmail.com"


@pytest.fixture(autouse=True)
def auth_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    monkeypatch.setenv("FOUNDRY_ALLOWED_EMAIL", ALLOWED)
    monkeypatch.setenv("SESSION_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.delenv("FOUNDRY_DEMO_DATA", raising=False)
    monkeypatch.delenv("FOUNDRY_DATA_PATH", raising=False)
    yield


def _client() -> TestClient:
    c = TestClient(app)
    c.cookies.set(webauth.SESSION_COOKIE, webauth.session_token(ALLOWED, webauth.load_config()))
    return c


# ---------------------------------------------------------------- gating

def test_demo_mode_absent_leaves_missing_log_untouched(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    # FOUNDRY_DEMO_DATA left unset (deleted by the autouse fixture).
    _maybe_seed_demo_data()
    assert not path.exists()


@pytest.mark.parametrize("value", ["false", "0", "False", "", "yes", "TRUE", "True",
                                    " true ", "1", "enabled", "on", "true\n"])
def test_demo_mode_requires_exactly_true(monkeypatch, tmp_path, value):
    """RFC-003.3A: only the literal lowercase, unpadded string "true"
    enables demo mode — no truthy-looking value ("TRUE", "1", "yes",
    "enabled", padded variants) may ever seed by accident."""
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", value)
    _maybe_seed_demo_data()
    assert not path.exists()


# --------------------------------------------------------------- seeding

def test_demo_mode_enabled_seeds_an_empty_log(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    _maybe_seed_demo_data()
    assert path.exists()
    events = list(EventLog(path).events())
    assert len(events) > 0
    assert any(e["kind"] == "core.mission.declared" for e in events)


def test_demo_mode_enabled_seeds_a_missing_log(monkeypatch, tmp_path):
    """The path's parent directory doesn't exist yet either — the same
    condition a fresh Render disk starts in."""
    path = tmp_path / "nested" / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    _maybe_seed_demo_data()
    assert path.exists()
    assert sum(1 for _ in EventLog(path).events()) > 0


def test_demo_mode_enabled_does_not_modify_a_non_empty_log(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append("core.party.declared", {"entity_id": "not-really-synthetic", "party_type": "household"})
    before = path.read_bytes()

    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    seeded = ensure_demo_data(str(path))

    assert seeded is False
    assert path.read_bytes() == before  # byte-for-byte: never overwritten, truncated, or appended to


def test_repeated_startup_does_not_duplicate_events(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")

    _maybe_seed_demo_data()
    first_count = sum(1 for _ in EventLog(path).events())
    first_bytes = path.read_bytes()

    _maybe_seed_demo_data()
    second_count = sum(1 for _ in EventLog(path).events())

    assert second_count == first_count
    assert path.read_bytes() == first_bytes


def test_ensure_demo_data_return_value_distinguishes_seeded_from_skipped(tmp_path):
    path = tmp_path / "events.jsonl"
    assert ensure_demo_data(str(path)) is True   # first call: was empty, seeded
    assert ensure_demo_data(str(path)) is False  # second call: already had events


# ------------------------------------------------- atomicity (RFC-003.3A F1)

def test_crash_mid_seed_leaves_target_untouched_and_recoverable(monkeypatch, tmp_path):
    """Seeding builds into a temp sibling and atomically renames — so a
    crash partway through must leave the target with no content (not a
    valid-looking half dataset that would be skipped forever), and the
    next start must seed cleanly."""
    path = tmp_path / "events.jsonl"

    real_build = demo_data.build

    def crashing_build(log, as_of=None):
        for i in range(5):
            log.append("core.party.declared", {"entity_id": f"partial-{i}", "party_type": "person"})
        raise RuntimeError("simulated crash mid-seed")

    monkeypatch.setattr(demo_data, "build", crashing_build)
    with pytest.raises(RuntimeError, match="simulated crash"):
        ensure_demo_data(str(path))

    # The target holds nothing: either absent or zero bytes. The partial
    # write went to an inert .tmp-<pid> sibling, never to the log itself.
    assert (not path.exists()) or path.stat().st_size == 0
    tmp_siblings = list(tmp_path.glob("events.jsonl.tmp-*"))
    assert tmp_siblings, "partial build should be in a temp sibling"

    # Recovery: the very next start seeds the full dataset.
    monkeypatch.setattr(demo_data, "build", real_build)
    assert ensure_demo_data(str(path)) is True
    assert EventLog(path).verify()
    assert sum(1 for _ in EventLog(path).events()) > 500


def test_seeded_log_arrives_hash_chain_valid(tmp_path):
    path = tmp_path / "events.jsonl"
    assert ensure_demo_data(str(path)) is True
    assert EventLog(path).verify()


# ------------------------------------------------ concurrency (RFC-003.3A F2)

def test_two_concurrent_processes_seed_exactly_one_dataset(tmp_path):
    """Two real OS processes racing on the same empty path (the
    multi-worker / overlapping-deploy case) must produce exactly one
    household, a single-seed event count, and an intact hash chain —
    never an interleaved double dataset."""
    repo_root = Path(__file__).resolve().parents[1]
    path = tmp_path / "events.jsonl"
    go_flag = tmp_path / "go"
    runner = f"""
import os, sys, time
sys.path.insert(0, {str(repo_root / 'src')!r})
from foundry.demo_data import ensure_demo_data
while not os.path.exists({str(go_flag)!r}):
    time.sleep(0.005)
ensure_demo_data({str(path)!r})
"""
    procs = [subprocess.Popen([sys.executable, "-c", runner]) for _ in range(2)]
    go_flag.touch()  # release both as close to simultaneously as possible
    for p in procs:
        assert p.wait(timeout=120) == 0

    log = EventLog(path)
    events = list(log.events())
    households = [e for e in events if e["kind"] == "core.party.declared"
                  and e["payload"].get("party_type") == "household"]
    missions = [e for e in events if e["kind"] == "core.mission.declared"]
    assert len(households) == 1, "concurrent seeding produced a doubled dataset"
    assert len(missions) == 1
    assert log.verify(), "concurrent seeding corrupted the hash chain"


def test_existing_lock_file_skips_seeding(tmp_path):
    path = tmp_path / "events.jsonl"
    lock = tmp_path / "events.jsonl.lock"
    lock.write_text("12345\n")
    assert ensure_demo_data(str(path)) is False
    assert (not path.exists()) or path.stat().st_size == 0
    assert lock.exists()  # never deletes a lock it didn't create


def test_stale_temp_sibling_is_not_mistaken_for_the_log(tmp_path):
    """A leftover .tmp-<pid> from a crashed earlier seed must neither
    block a fresh seed nor be treated as the event log."""
    path = tmp_path / "events.jsonl"
    (tmp_path / "events.jsonl.tmp-99999").write_text("{garbage from a dead process\n")
    assert ensure_demo_data(str(path)) is True
    assert EventLog(path).verify()


# ---------------------------------- unknown data preserved (RFC-003.3A F3/F8)

@pytest.mark.parametrize("content,label", [
    (b"   \n\n  \n", "whitespace-only"),
    (b"this is not json\n", "malformed"),
    (b'{"id": "x", "ts": 1.0, "kind": "core.party.declared", "actor": "user", '
     b'"payload": {}, "prev_hash": "0"}\n{"partial', "partially written final line"),
])
def test_non_empty_but_invalid_content_is_preserved_untouched(tmp_path, content, label, caplog):
    """Any existing bytes — even ones that don't parse as an event log —
    are evidence, never seeded over, never 'repaired'. The skip is
    logged at critical severity so the operator finds out."""
    path = tmp_path / "events.jsonl"
    path.write_bytes(content)
    with caplog.at_level("INFO", logger="foundry.demo_data"):
        assert ensure_demo_data(str(path)) is False, label
    assert path.read_bytes() == content, label
    assert any("does not parse/verify" in r.message for r in caplog.records), label


def test_corrupted_hash_chain_is_preserved_untouched(tmp_path, caplog):
    path = tmp_path / "events.jsonl"
    ensure_demo_data(str(path))
    lines = path.read_text().splitlines()
    tampered = json.loads(lines[3])
    tampered["actor"] = "tampered"  # valid JSON, broken hash
    lines[3] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    evidence = path.read_bytes()

    with caplog.at_level("INFO", logger="foundry.demo_data"):
        assert ensure_demo_data(str(path)) is False
    assert path.read_bytes() == evidence
    assert any("does not parse/verify" in r.message for r in caplog.records)


def test_path_that_is_a_directory_fails_visibly(tmp_path):
    target_dir = tmp_path / "events.jsonl"
    target_dir.mkdir()
    with pytest.raises(IsADirectoryError):
        ensure_demo_data(str(target_dir))
    assert target_dir.is_dir()  # untouched


# --------------------------------------- synthetic marker (RFC-003.3A F5)

def test_seeded_log_carries_a_permanent_synthetic_marker(tmp_path):
    """The file itself must say it is synthetic — in-band, replayable,
    greppable — so it can never be confused with a real household even
    with all documentation gone."""
    path = tmp_path / "events.jsonl"
    ensure_demo_data(str(path))
    events = list(EventLog(path).events())
    markers = [e for e in events if e["kind"] == "claim.derived"
               and e["actor"] == "synthetic_demo"
               and e["payload"]["statement"].startswith("SYNTHETIC DEMO DATA")]
    assert len(markers) == 1
    # And raw grep-ability, independent of any Foundry code:
    assert b"SYNTHETIC DEMO DATA" in path.read_bytes()


def test_synthetic_marker_does_not_pollute_next_decision(monkeypatch, tmp_path):
    """The marker is tagged `observation`, so the Flight Deck's
    NEXT DECISION slot (recommendations only) must still surface the
    real recommendation, not the marker."""
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    _maybe_seed_demo_data()
    html = _client().get("/").text
    assert "SYNTHETIC DEMO DATA" not in html
    assert "standing quarterly check" in html  # the actual recommendation


# ------------------------------------------------------------- fail closed

def test_unwritable_path_fails_visibly(tmp_path):
    """A read-only parent directory must raise, not silently no-op —
    'fail closed' means the process refuses to start looking healthy
    when the demo data it was asked for couldn't be written."""
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x, no write
    target = readonly_dir / "nested" / "events.jsonl"  # parent must be *created*
    try:
        with pytest.raises(OSError):
            ensure_demo_data(str(target))
    finally:
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)  # restore for cleanup


def test_maybe_seed_demo_data_propagates_the_failure(monkeypatch, tmp_path):
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    target = readonly_dir / "nested" / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(target))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    try:
        with pytest.raises(OSError):
            _maybe_seed_demo_data()
    finally:
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)


# ------------------------------------------------------- no public trigger

def test_no_route_exposes_demo_seeding(monkeypatch, tmp_path):
    """Demo mode must only run at process startup, in-process — never
    reachable by an HTTP request, seeded or not."""
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    c = _client()
    for candidate in ("/seed", "/demo", "/demo-data", "/admin/seed", "/_seed"):
        r = c.get(candidate)
        assert r.status_code in (404, 303)
    # And nothing about visiting real routes seeds anything on its own —
    # only the explicit startup call does.
    assert not path.exists()


# ---------------------------------------------------------- Mission Control

def test_seeded_log_renders_populated_mission_control(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("FOUNDRY_DATA_PATH", str(path))
    monkeypatch.setenv("FOUNDRY_DEMO_DATA", "true")
    _maybe_seed_demo_data()

    r = _client().get("/")
    assert r.status_code == 200
    assert "Coast FIRE by 2038" in r.text
    assert "UNSUPPORTED" not in r.text
    assert r.text.count("£") >= 2


# --------------------------------------------------------------- git hygiene

def test_default_data_path_is_git_ignored():
    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(["git", "check-ignore", "-q", DEFAULT_DATA_PATH],
                             cwd=repo_root)
    assert result.returncode == 0, f"{DEFAULT_DATA_PATH} is not git-ignored"


def test_seeding_the_default_path_produces_no_git_status_change():
    """End-to-end version of the hygiene check above: actually seed
    FOUNDRY_DEMO_DATA's real default path inside the working tree and
    confirm `git status --porcelain` reports no change either way —
    before seeding (already ignored) and after (still ignored)."""
    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("not a git checkout")
    full_path = repo_root / DEFAULT_DATA_PATH
    existed_before = full_path.exists()
    before_bytes = full_path.read_bytes() if existed_before else None

    status_before = subprocess.run(["git", "status", "--porcelain", DEFAULT_DATA_PATH],
                                    cwd=repo_root, capture_output=True, text=True).stdout
    assert status_before.strip() == ""

    ensure_demo_data(str(full_path))

    status_after = subprocess.run(["git", "status", "--porcelain", DEFAULT_DATA_PATH],
                                   cwd=repo_root, capture_output=True, text=True).stdout
    assert status_after.strip() == ""

    if not existed_before:
        full_path.unlink()
        parent = full_path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    elif before_bytes is not None:
        full_path.write_bytes(before_bytes)  # leave any pre-existing local file exactly as found
