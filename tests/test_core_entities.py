"""Unit + regression tests: Party, Employer, Mission as a projection
over `core.*` events (000 §8)."""

from foundry.core.entities import EntityProjection, declare_employer, declare_mission, \
    declare_party, employ, join_household, update_party


def test_household_party_never_holds_resources_is_a_convention_not_enforced_here():
    """000 §8's rule ('a group-type Party is never itself the holder of
    a domain's resources') is enforced by the *ownership* vocabulary a
    domain defines — Core has none, so this is documented, not tested,
    here. See 001 §9 for Finance's enforcement of the same rule."""


def test_party_declared_and_projected(kernel):
    household = declare_party(kernel.log, "household")
    projection = EntityProjection(kernel.log)
    assert projection.parties[household.id].party_type == "household"
    assert projection.parties[household.id].status == "active"


def test_household_membership_and_group_expansion(kernel):
    household = declare_party(kernel.log, "household")
    chris = declare_party(kernel.log, "person")
    fiona = declare_party(kernel.log, "person")
    join_household(kernel.log, chris.id, household.id)
    join_household(kernel.log, fiona.id, household.id)

    projection = EntityProjection(kernel.log)
    members = {p.id for p in projection.members_of(household.id)}
    assert members == {chris.id, fiona.id}


def test_update_party_attaches_domain_attribute_to_the_one_stream(kernel):
    """A dependent domain (Finance) attaches `reporting_currency` to
    the Household Party via the *same* core.party.* stream — no
    domain-prefixed shadow event kind exists (000 §5, principle 3)."""
    household = declare_party(kernel.log, "household")
    update_party(kernel.log, household.id, {"reporting_currency": "GBP"}, reason="set default")

    projection = EntityProjection(kernel.log)
    assert projection.parties[household.id].attributes["reporting_currency"] == "GBP"
    kinds = {e["kind"] for e in kernel.log.events()}
    assert kinds == {"core.party.declared", "core.party.updated"}
    assert not any(k.startswith("finance.") for k in kinds)


def test_employer_declared_and_employment_link(kernel):
    acme = declare_employer(kernel.log, "Acme Corp", industry="widgets")
    chris = declare_party(kernel.log, "person")
    employ(kernel.log, chris.id, acme.id)

    projection = EntityProjection(kernel.log)
    assert projection.employers[acme.id].name == "Acme Corp"
    assert projection.parties[chris.id].employers == [acme.id]


def test_mission_declared_with_target(kernel):
    m = declare_mission(kernel.log, "House deposit", target_metric="finance.net_worth",
                         target_value=60000.0, tolerance=2000.0)
    projection = EntityProjection(kernel.log)
    mission = projection.missions[m.id]
    assert mission.target_metric == "finance.net_worth"
    assert mission.target_value == 60000.0
    assert mission.status == "active"


def test_mission_achieved_vs_abandoned_are_distinguishable(kernel):
    """Both are terminal states reached via the same `.closed` verb,
    distinguished by payload, not by inventing a sixth verb."""
    achieved = declare_mission(kernel.log, "Emergency fund")
    abandoned = declare_mission(kernel.log, "Buy a boat")
    from foundry.core.entities import abandon_mission, achieve_mission
    achieve_mission(kernel.log, achieved.id, reason="target reached")
    abandon_mission(kernel.log, abandoned.id, reason="no longer relevant")

    projection = EntityProjection(kernel.log)
    assert projection.missions[achieved.id].status == "achieved"
    assert projection.missions[abandoned.id].status == "abandoned"


def test_close_with_status_vocabulary_rejects_ungoverned_value(kernel):
    """The write path a bare grammar.close() call could otherwise use
    to bypass mission_status governance entirely — validated the same
    way relate() already validates relations."""
    import pytest

    from foundry.core import grammar, vocab
    from foundry.errors import VocabularyError

    mission = declare_mission(kernel.log, "Test mission")
    with pytest.raises(VocabularyError):
        grammar.close(kernel.log, "core", "mission", mission.id, "reason",
                       status="not_a_real_status", status_vocabulary=vocab.MISSION_STATUS)


def test_achieve_and_abandon_mission_are_governed_by_mission_status_vocabulary(kernel):
    from foundry.core.entities import abandon_mission, achieve_mission

    achieved = declare_mission(kernel.log, "Achieved one")
    achieve_mission(kernel.log, achieved.id)
    e = list(kernel.log.events())[-1]
    assert e["payload"]["status"] == "achieved"

    abandoned = declare_mission(kernel.log, "Abandoned one")
    abandon_mission(kernel.log, abandoned.id)
    e2 = list(kernel.log.events())[-1]
    assert e2["payload"]["status"] == "abandoned"


def test_rebuild_equals_incremental_apply(kernel):
    """REGRESSION ORACLE, mirrored from test_canon.py: apply() is an
    optimisation and must never diverge from rebuild()."""
    household = declare_party(kernel.log, "household")
    chris = declare_party(kernel.log, "person")
    join_household(kernel.log, chris.id, household.id)
    acme = declare_employer(kernel.log, "Acme Corp")
    employ(kernel.log, chris.id, acme.id)
    declare_mission(kernel.log, "Retire at 60", target_metric="finance.net_worth")

    incremental = EntityProjection(kernel.log)
    snapshot = {
        "parties": {k: vars(v).copy() for k, v in incremental.parties.items()},
        "employers": {k: vars(v).copy() for k, v in incremental.employers.items()},
        "missions": {k: vars(v).copy() for k, v in incremental.missions.items()},
    }
    incremental.rebuild()
    rebuilt = {
        "parties": {k: vars(v).copy() for k, v in incremental.parties.items()},
        "employers": {k: vars(v).copy() for k, v in incremental.employers.items()},
        "missions": {k: vars(v).copy() for k, v in incremental.missions.items()},
    }
    assert snapshot == rebuilt


def test_deterministic_replay_two_independent_projections(kernel):
    household = declare_party(kernel.log, "household")
    join_household(kernel.log, declare_party(kernel.log, "person").id, household.id)

    a = EntityProjection(kernel.log)
    b = EntityProjection(kernel.log)
    assert {k: vars(v) for k, v in a.parties.items()} == {k: vars(v) for k, v in b.parties.items()}
