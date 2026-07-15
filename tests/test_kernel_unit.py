"""Unit tests: kernel edge behaviour."""

import pytest
from foundry.errors import EventNotFoundError


def test_derive_unknown_event_raises(kernel):
    with pytest.raises(EventNotFoundError):
        kernel.derive("no-such-event")


def test_derive_non_ingest_event_raises(kernel):
    e = kernel.ingest("Alice is here.")
    claim = kernel.derive(e["id"])[0]
    derive_event = claim.history[0]
    with pytest.raises(EventNotFoundError):
        kernel.derive(derive_event)


def test_retrieve_on_empty_substrate(kernel):
    r = kernel.retrieve("anything")
    assert r == {"events": [], "claims": [], "provenance": {}}


def test_ask_with_no_knowledge(kernel):
    r = kernel.ask("What is the budget?")
    assert r["citations"] == []
    assert "answer" in r
