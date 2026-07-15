"""Unit + regression tests: Canon as pure projection."""

from foundry.models import MockModelBeta


def test_incremental_apply_equals_full_rebuild(kernel):
    """REGRESSION ORACLE: apply() is an optimisation and must never
    diverge from rebuild(). If this test fails, incremental state
    maintenance has a bug."""
    e = kernel.ingest("Alice is the lead. The budget is 40000 pounds.")
    claims = kernel.derive(e["id"])
    kernel.update_claim(claims[0].id, confidence=0.95, reason="confirmed")
    kernel.link(claims[0].id, "relates_to", claims[1].id)
    kernel.resolve_conflict(claims[1].id, claims[0].id, reason="test")

    incremental = {c.id: c.to_dict() for c in kernel.canon.claims.values()}
    kernel.canon.rebuild()
    rebuilt = {c.id: c.to_dict() for c in kernel.canon.claims.values()}
    assert incremental == rebuilt


def test_deterministic_replay(kernel, tmp_path):
    """Same log, two independent Canons, identical state — replay is
    deterministic because no model is involved in projection."""
    e = kernel.ingest("Bob prefers the second proposal.")
    kernel.derive(e["id"])
    from foundry.canon import Canon
    fresh = Canon(kernel.log)
    assert {c.id: c.to_dict() for c in fresh.claims.values()} == \
           {c.id: c.to_dict() for c in kernel.canon.claims.values()}


def test_update_unknown_claim_is_harmless(kernel):
    kernel.update_claim("nonexistent-id", confidence=0.1, reason="noise")
    assert kernel.canon.get("nonexistent-id") is None
    assert kernel.log.verify()


def test_explain_unknown_claim_returns_none(kernel):
    assert kernel.why("nope") is None
