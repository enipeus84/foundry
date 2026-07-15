"""
Tests are organised around the seven success criteria in the brief,
not around code units. Each test is an architectural claim.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foundry.eventlog import EventLog
from foundry.kernel import Kernel
from foundry.models import MockModelAlpha, MockModelBeta

SAMPLE = (
    "Alice is the head of research at Acme. "
    "The Q3 budget was 40000 pounds. "
    "Does anyone know when the review happens? "
    "Bob prefers the second proposal."
)


def make_kernel(tmp_path):
    return Kernel(EventLog(tmp_path / "events.jsonl"), MockModelAlpha())


def test_1_import_and_2_preserve_forever(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE, source="meeting-notes")
    stored = k.log.get(e["id"])
    assert stored["payload"]["text"] == SAMPLE          # original intact
    assert k.log.verify()                               # chain valid


def test_3_extract_structured_claims(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    claims = k.derive(e["id"])
    assert len(claims) >= 3
    assert all(c.statement and 0 < c.confidence <= 1 for c in claims)
    assert not any("?" in c.statement for c in claims)  # questions aren't facts


def test_4_provenance_on_every_claim(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    for c in k.derive(e["id"]):
        why = k.why(c.id)
        assert why["source_events"][0]["id"] == e["id"]   # traceable to source
        assert why["derived_by"] == "mock-alpha"          # model in provenance
        assert why["evidence"]                            # verbatim support


def test_5_memory_is_derived_state_not_history(tmp_path):
    """Delete the Canon; replaying the log reproduces it exactly."""
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    k.derive(e["id"])
    before = {c.id: c.statement for c in k.canon.active()}
    k.canon.claims = {}          # destroy derived state
    k.canon.rebuild()            # replay events
    after = {c.id: c.statement for c in k.canon.active()}
    assert before == after


def test_6_and_7_swap_model_continue_seamlessly(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    alpha_claims = k.derive(e["id"])

    k.swap_model(MockModelBeta())               # one line: the whole swap

    # Old state fully usable by the new model
    r = k.ask("Who is head of research?")
    assert "Alice" in r["answer"]
    assert r["model"] == "mock-beta"
    assert any(c["derived_by"] == "mock-alpha" for c in r["citations"])

    # New model can keep deriving into the same substrate
    e2 = k.ingest("Carol has 3 direct reports.")
    beta_claims = k.derive(e2["id"])
    assert beta_claims and beta_claims[0].derived_by == "mock-beta"

    # Both models' work coexists with distinct provenance
    actors = {c.derived_by for c in k.canon.active()}
    assert actors == {"mock-alpha", "mock-beta"}


def test_claims_evolve_events_never_do(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    c = k.derive(e["id"])[0]
    n_events_before = sum(1 for _ in k.log.events())

    k.update_claim(c.id, confidence=0.95, reason="confirmed by second source")

    updated = k.canon.get(c.id)
    assert updated.confidence == 0.95
    # Evolution happened via a NEW event, not mutation:
    assert sum(1 for _ in k.log.events()) == n_events_before + 1
    assert len(updated.history) == 2
    assert k.log.verify()


def test_conflict_resolution_preserves_loser(tmp_path):
    k = make_kernel(tmp_path)
    e1 = k.ingest("The budget is 40000 pounds.")
    e2 = k.ingest("The budget is 50000 pounds.")
    a = k.derive(e1["id"])[0]
    b = k.derive(e2["id"])[0]
    k.resolve_conflict(a.id, b.id, reason="e2 is more recent")
    assert k.canon.get(a.id).status == "superseded"
    assert k.canon.get(a.id).superseded_by == b.id
    assert k.why(a.id) is not None       # losing claim still fully explainable


def test_retrieval_returns_provenance_not_chunks(tmp_path):
    k = make_kernel(tmp_path)
    e = k.ingest(SAMPLE)
    k.derive(e["id"])
    r = k.retrieve("research Alice")
    assert r["claims"] and r["events"]
    first = r["claims"][0]
    assert r["provenance"][first.id]["source_events"][0]["id"] == e["id"]


def test_tamper_detection(tmp_path):
    k = make_kernel(tmp_path)
    k.ingest("original truth")
    p = tmp_path / "events.jsonl"
    p.write_text(p.read_text().replace("original truth", "edited truth"))
    assert not k.log.verify()


# ---------------------------------------------------------------- V1.0 tests

from foundry.ingestors import ingest_file, ingest_chatgpt_export, ingest_claude_export
import json as _json


def test_ingest_file_preserves_verbatim(tmp_path):
    k = make_kernel(tmp_path)
    doc = tmp_path / "note.md"
    doc.write_text("# Notes\nThe boiler service is due in October.\n")
    events = ingest_file(k, doc)
    assert events[0]["payload"]["text"] == doc.read_text()
    assert events[0]["payload"]["source"] == "file:note.md"


def test_ingest_chatgpt_export(tmp_path):
    k = make_kernel(tmp_path)
    export = tmp_path / "conversations.json"
    export.write_text(_json.dumps([{
        "title": "budget chat",
        "mapping": {
            "n1": {"message": {"author": {"role": "user"},
                               "content": {"parts": ["The budget is 5000."]}}},
            "n2": {"message": {"author": {"role": "assistant"},
                               "content": {"parts": ["Noted."]}}},
            "n3": {"message": None},
        },
    }]))
    events = ingest_chatgpt_export(k, export)
    assert len(events) == 1
    assert "budget is 5000" in events[0]["payload"]["text"]
    assert events[0]["payload"]["source"] == "chatgpt:budget chat"


def test_ingest_claude_export(tmp_path):
    k = make_kernel(tmp_path)
    export = tmp_path / "claude.json"
    export.write_text(_json.dumps([{
        "name": "planning",
        "chat_messages": [{"sender": "human", "text": "Alice is the lead."}],
    }]))
    events = ingest_claude_export(k, export)
    assert events and "Alice is the lead" in events[0]["payload"]["text"]


def test_underived_tracks_per_model(tmp_path):
    k = make_kernel(tmp_path)
    e1 = k.ingest("Fact one is true.")
    e2 = k.ingest("Fact two is true.")
    k.derive(e1["id"])
    pending = k.underived(by_model="mock-alpha")
    assert [e["id"] for e in pending] == [e2["id"]]
    # A different model has derived nothing yet:
    assert len(k.underived(by_model="mock-beta")) == 2


def test_defensive_claim_parsing():
    from foundry.models import _parse_claims
    assert _parse_claims("no json here") == []
    got = _parse_claims('preamble [{"statement":"s is t","confidence":9,"evidence":"s is t"}] suffix')
    assert got[0].confidence == 1.0
