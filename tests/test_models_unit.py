"""Unit tests: model adapters and defensive parsing."""

from foundry.models import MockModelAlpha, MockModelBeta, _parse_claims


def test_alpha_ignores_questions_and_non_facts():
    claims = MockModelAlpha().extract_claims(
        "Is Alice the lead? Hello there. Alice is the lead."
    )
    assert len(claims) == 1
    assert "Alice is the lead" in claims[0].statement


def test_beta_catches_numerics_alpha_misses():
    text = "Deliver 12 units by Friday."
    assert MockModelAlpha().extract_claims(text) == []
    assert len(MockModelBeta().extract_claims(text)) == 1


def test_parse_claims_strips_fences():
    got = _parse_claims('```json\n[{"statement":"a is b","confidence":0.5,"evidence":"a is b"}]\n```')
    assert len(got) == 1


def test_parse_claims_clamps_confidence():
    got = _parse_claims('[{"statement":"x","confidence":-3,"evidence":"x"}]')
    assert got[0].confidence == 0.0


def test_parse_claims_skips_malformed_items():
    got = _parse_claims('[{"statement":"ok","confidence":0.5,"evidence":"ok"},{"nope":1}]')
    assert len(got) == 1


def test_parse_claims_garbage_is_empty():
    assert _parse_claims("I'm sorry, I can't help with that.") == []
