"""Unit tests: the event log's core guarantees."""

from foundry.eventlog import EventLog, GENESIS_HASH


def test_empty_log_verifies(tmp_path):
    assert EventLog(tmp_path / "e.jsonl").verify()


def test_first_event_chains_to_genesis(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    e = log.append("ingest", {"text": "x"})
    assert e["prev_hash"] == GENESIS_HASH


def test_append_is_consistent_across_reopen(tmp_path):
    """The cached last-hash must equal what a fresh scan would find."""
    p = tmp_path / "e.jsonl"
    log = EventLog(p)
    log.append("ingest", {"text": "one"})
    reopened = EventLog(p)               # forces a scan
    reopened.append("ingest", {"text": "two"})
    assert reopened.verify()


def test_unicode_survives_round_trip(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    text = "Bücher kosten 40 £ — naïve café ☕"
    e = log.append("ingest", {"text": text})
    assert log.get(e["id"])["payload"]["text"] == text
    assert log.verify()


def test_edit_detection(tmp_path):
    p = tmp_path / "e.jsonl"
    log = EventLog(p)
    log.append("ingest", {"text": "truth"})
    p.write_text(p.read_text().replace("truth", "lies"))
    assert not log.verify()


def test_insertion_detection(tmp_path):
    p = tmp_path / "e.jsonl"
    log = EventLog(p)
    log.append("ingest", {"text": "a"})
    log.append("ingest", {"text": "b"})
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[0], lines[0], lines[1]]) + "\n")
    assert not log.verify()
