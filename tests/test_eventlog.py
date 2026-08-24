"""Unit tests: the event log's core guarantees."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_append_uses_actual_tail_across_stale_instances(tmp_path):
    path = tmp_path / "e.jsonl"
    first = EventLog(path)
    second = EventLog(path)

    event_one = first.append("ingest", {"text": "one"})
    event_two = second.append("ingest", {"text": "two"})

    events = list(EventLog(path).events())
    assert event_one["prev_hash"] == GENESIS_HASH
    assert event_two["prev_hash"] == event_one["hash"]
    assert [event["hash"] for event in events] == [event_one["hash"], event_two["hash"]]
    assert EventLog(path).verify()


def test_concurrent_writers_cannot_claim_same_parent(tmp_path):
    path = tmp_path / "e.jsonl"
    first = EventLog(path)
    second = EventLog(path)
    barrier = Barrier(2)

    def append(log: EventLog, text: str) -> dict:
        barrier.wait()
        return log.append("ingest", {"text": text})

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(append, first, "one")
        future_two = executor.submit(append, second, "two")
        event_one = future_one.result()
        event_two = future_two.result()

    events = list(EventLog(path).events())
    hashes = {event_one["hash"], event_two["hash"]}

    assert len(events) == 2
    assert {event["hash"] for event in events} == hashes
    assert events[0]["prev_hash"] == GENESIS_HASH
    assert events[1]["prev_hash"] == events[0]["hash"]
    assert {event_one["prev_hash"], event_two["prev_hash"]} == {GENESIS_HASH, events[0]["hash"]}
    assert EventLog(path).verify()
