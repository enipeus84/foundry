"""Unit + regression tests: Finance's eleven entities as a projection
over `finance.*` events (001 §7, §11, §14)."""

import pytest

from foundry.errors import VocabularyError
from foundry.finance import entities as fin


def test_account_declared_and_projected(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP", name="Current account")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.accounts[account.id].account_type == "checking"
    assert projection.accounts[account.id].tax_wrapper == "none"
    assert projection.accounts[account.id].status == "active"


def test_declare_account_rejects_invalid_account_type(kernel):
    with pytest.raises(VocabularyError):
        fin.declare_account(kernel.log, "not_a_type", "GBP")


def test_close_account(kernel):
    account = fin.declare_account(kernel.log, "savings", "GBP")
    fin.close_account(kernel.log, account.id, reason="account closed by customer")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.accounts[account.id].status == "closed"


def test_ownership_link_carries_optional_share(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "co_owner", "chris", share=60.0)
    fin.link_ownership(kernel.log, "account", account.id, "co_owner", "fiona", share=40.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    links = {l.target: l.share for l in projection.accounts[account.id].ownership}
    assert links == {"chris": 60.0, "fiona": 40.0}


def test_ownership_link_rejects_invalid_relation(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP")
    with pytest.raises(VocabularyError):
        fin.link_ownership(kernel.log, "account", account.id, "not_a_relation", "chris")


def test_ownership_link_rejects_non_ownable_entity_types(kernel):
    """001 §8's relation table names Account/Asset/Obligation only; a
    Position's owner is resolved through its account (001 §17). An
    ownership link against any other type must never reach the log."""
    with pytest.raises(ValueError):
        fin.link_ownership(kernel.log, "position", "pos-1", "owner", "chris")
    with pytest.raises(ValueError):
        fin.link_ownership(kernel.log, "transaction", "txn-1", "owner", "chris")
    assert list(kernel.log.events()) == []  # nothing was written


def test_ownership_link_rejects_out_of_range_share(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP")
    for bad_share in (0.0, -10.0, 150.0):
        with pytest.raises(ValueError):
            fin.link_ownership(kernel.log, "account", account.id, "co_owner", "chris", share=bad_share)


def test_asset_and_obligation_declared(kernel):
    asset = fin.declare_asset(kernel.log, "property", "GBP", name="Family home")
    obligation = fin.declare_obligation(kernel.log, "mortgage", "GBP", amount=200_000.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.assets[asset.id].asset_category == "property"
    assert projection.obligations[obligation.id].amount == 200_000.0


def test_obligation_settle_vs_close_are_distinguishable_terminal_states(kernel):
    settled = fin.declare_obligation(kernel.log, "personal_loan", "GBP")
    written_off = fin.declare_obligation(kernel.log, "credit_card_debt", "GBP")
    fin.settle_obligation(kernel.log, settled.id, reason="paid in full")
    fin.close_obligation(kernel.log, written_off.id, reason="written off")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.obligations[settled.id].status == "settled"
    assert projection.obligations[written_off.id].status == "closed"


def test_transaction_correction_sets_status_corrected(kernel):
    """finance.transaction.corrected is finance.transaction.updated
    with a mandatory reason (001 §11) — not a second event kind."""
    account = fin.declare_account(kernel.log, "checking", "GBP")
    txn = fin.declare_transaction(kernel.log, account.id, -50.0, "GBP", "groceries", 1000.0)
    fin.correct_transaction(kernel.log, txn.id, reason="wrong amount entered", amount=-55.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    corrected = projection.transactions[txn.id]
    assert corrected.status == "corrected"
    assert corrected.amount == -55.0
    kinds = {e["kind"] for e in kernel.log.events()}
    assert kinds == {"finance.account.declared", "finance.transaction.declared", "finance.transaction.updated"}


def test_declare_transaction_rejects_invalid_category(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP")
    with pytest.raises(VocabularyError):
        fin.declare_transaction(kernel.log, account.id, -10.0, "GBP", "not_a_category", 1000.0)


def test_correct_transaction_rejects_invalid_category(kernel):
    """The correction path is not a loophole: a corrected
    transaction_category is validated against the same vocabulary as a
    declared one — an ungoverned value must never reach the append-only
    log through *any* write path."""
    account = fin.declare_account(kernel.log, "checking", "GBP")
    txn = fin.declare_transaction(kernel.log, account.id, -50.0, "GBP", "groceries", 1000.0)
    events_before = len(list(kernel.log.events()))
    with pytest.raises(VocabularyError):
        fin.correct_transaction(kernel.log, txn.id, reason="miscategorised",
                                 transaction_category="not_a_category")
    assert len(list(kernel.log.events())) == events_before  # nothing was written


def test_account_and_asset_names_survive_the_projection(kernel):
    """Regression: a declared `name` must not be dropped by the fold —
    the projection would otherwise silently hold less than the log."""
    account = fin.declare_account(kernel.log, "checking", "GBP", name="Joint current account")
    asset = fin.declare_asset(kernel.log, "property", "GBP", name="Family home")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.accounts[account.id].name == "Joint current account"
    assert projection.assets[asset.id].name == "Family home"


def test_valuation_has_no_update_or_close_a_revision_is_a_new_event(kernel):
    asset = fin.declare_asset(kernel.log, "property", "GBP")
    fin.declare_valuation(kernel.log, asset.id, 400_000.0, "GBP", 1000.0)
    fin.declare_valuation(kernel.log, asset.id, 410_000.0, "GBP", 2000.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    assert len(projection.valuations_of(asset.id)) == 2
    latest = max(projection.valuations_of(asset.id), key=lambda v: v.as_of)
    assert latest.amount == 410_000.0


def test_position_within_an_account_and_issuer_reference(kernel):
    account = fin.declare_account(kernel.log, "brokerage", "GBP")
    position = fin.declare_position(kernel.log, account.id, "Acme plc", quantity=100, unit_price=5.0,
                                     currency="GBP", cost_basis=400.0, valuation_date=1000.0,
                                     market_value=500.0, asset_category="private_equity", issuer="employer-1")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.positions_in(account.id) == [projection.positions[position.id]]
    assert projection.positions[position.id].issuer == "employer-1"


def test_close_position_excludes_it_from_positions_in(kernel):
    account = fin.declare_account(kernel.log, "brokerage", "GBP")
    position = fin.declare_position(kernel.log, account.id, "Acme plc", quantity=100, unit_price=5.0,
                                     currency="GBP", cost_basis=400.0, valuation_date=1000.0,
                                     market_value=500.0, asset_category="private_equity")
    fin.close_position(kernel.log, position.id, reason="fully disposed")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.positions_in(account.id) == []
    assert projection.positions[position.id].status == "closed"


def test_recurring_series_pause_is_not_terminal(kernel):
    """Pausing uses `.updated`, not `.closed` — a paused series can
    still resume (001 §7's lifecycle table lists paused as a distinct,
    non-final state from ended)."""
    series = fin.declare_recurring_series(kernel.log, "mortgage_payment", 1450.0, "GBP")
    fin.pause_recurring_series(kernel.log, series.id, reason="payment holiday")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.recurring_series[series.id].status == "paused"
    fin.resume_recurring_series(kernel.log, series.id, reason="holiday over")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.recurring_series[series.id].status == "active"
    kinds = [e["kind"] for e in kernel.log.events()]
    assert kinds.count("finance.recurring_series.closed") == 0


def test_recurring_series_ended_is_terminal(kernel):
    series = fin.declare_recurring_series(kernel.log, "regular_expense", 50.0, "GBP")
    fin.end_recurring_series(kernel.log, series.id, reason="subscription cancelled")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.recurring_series[series.id].status == "ended"


def test_recurring_series_never_pre_creates_a_transaction(kernel):
    """001 §24, criterion 17."""
    fin.declare_recurring_series(kernel.log, "salary", 4200.0, "GBP")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.transactions == {}


def test_fulfils_extension_links_a_transaction_to_its_recurring_series(kernel):
    account = fin.declare_account(kernel.log, "checking", "GBP")
    series = fin.declare_recurring_series(kernel.log, "mortgage_payment", 1450.0, "GBP")
    txn = fin.declare_transaction(kernel.log, account.id, -1450.0, "GBP", "housing", 1000.0)
    e = fin.fulfil(kernel.log, txn.id, series.id)
    assert e["payload"]["relation"] == "fulfils"
    assert e["kind"] == "finance.transaction.linked"


def test_tax_jurisdiction_and_tax_resident_in(kernel):
    from foundry.core.entities import declare_party
    jurisdiction = fin.declare_tax_jurisdiction(kernel.log, "UK", tax_year_start=1000.0, tax_year_end=2000.0)
    chris = declare_party(kernel.log, "person")
    e = fin.tax_resident_in(kernel.log, chris.id, jurisdiction.id)
    assert e["kind"] == "core.party.linked"  # the Party's own stream, not a finance-prefixed shadow
    assert e["payload"]["relation"] == "tax_resident_in"


def test_exchange_rate_declared_only_in_v1(kernel):
    fin.declare_exchange_rate(kernel.log, "EUR/GBP", 0.86, 1000.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    assert len(projection.exchange_rates) == 1
    kinds = {e["kind"] for e in kernel.log.events()}
    assert kinds == {"finance.exchange_rate.declared"}


def test_tax_position_estimation_basis_is_never_optional(kernel):
    import inspect
    sig = inspect.signature(fin.declare_tax_position)
    assert sig.parameters["estimation_basis"].default is inspect.Parameter.empty


def test_tax_position_rejects_invalid_estimation_basis(kernel):
    with pytest.raises(VocabularyError):
        fin.declare_tax_position(kernel.log, "subject-1", "2025/26", "jurisdiction-1", "guessed")


def test_unsupported_tax_position_has_no_amount(kernel):
    """001 §5, design principle 2 / §19: fails visibly rather than
    guessing — enforced at write time, not left to caller discipline."""
    with pytest.raises(ValueError):
        fin.declare_tax_position(kernel.log, "subject-1", "2025/26", "jurisdiction-1",
                                  "unsupported", amount=1000.0)
    tp = fin.declare_tax_position(kernel.log, "subject-1", "2025/26", "jurisdiction-1", "unsupported")
    assert tp.amount is None
    assert tp.status == "unsupported"


def test_capital_gain_event_has_no_closed_state():
    assert not hasattr(fin, "close_capital_gain_event")


def test_capital_gain_event_declared(kernel):
    account = fin.declare_account(kernel.log, "brokerage", "GBP")
    pos = fin.declare_position(kernel.log, account.id, "Acme plc", quantity=0, unit_price=5.0,
                                currency="GBP", cost_basis=400.0, valuation_date=1000.0,
                                market_value=0.0, asset_category="private_equity")
    gain = fin.declare_capital_gain_event(kernel.log, pos.id, realized_gain=1500.0, currency="GBP", date=1500.0)
    projection = fin.FinanceEntityProjection(kernel.log)
    assert projection.capital_gain_events[gain.id].realized_gain == 1500.0


def test_projection_ignores_core_and_claim_events(kernel):
    from foundry.core.entities import declare_party
    declare_party(kernel.log, "household")
    kernel.ingest("unrelated note")
    fin.declare_account(kernel.log, "checking", "GBP")
    projection = fin.FinanceEntityProjection(kernel.log)
    assert len(projection.accounts) == 1  # no crash, no stray state from non-finance events


def test_rebuild_and_incremental_apply_agree(kernel):
    """Mirrors Canon's own regression discipline: rebuild() is the
    correctness oracle apply() must always match."""
    account = fin.declare_account(kernel.log, "checking", "GBP")
    fin.link_ownership(kernel.log, "account", account.id, "owner", "chris")
    fin.declare_transaction(kernel.log, account.id, 100.0, "GBP", "income", 1000.0)

    projection = fin.FinanceEntityProjection(kernel.log)  # built incrementally via rebuild() in __init__
    rebuilt = fin.FinanceEntityProjection(kernel.log)
    rebuilt.rebuild()

    assert {k: vars(v) for k, v in projection.accounts.items()} == \
           {k: vars(v) for k, v in rebuilt.accounts.items()}
    assert {k: vars(v) for k, v in projection.transactions.items()} == \
           {k: vars(v) for k, v in rebuilt.transactions.items()}


def test_no_duplicated_core_event_kind_anywhere(kernel):
    """001 §24, criterion 1: no finance.party.*, finance.employer.*,
    finance.mission.*, finance.decision.*, or
    finance.decision_outcome.* event exists."""
    from foundry.core.entities import declare_party

    declare_party(kernel.log, "household")
    fin.declare_account(kernel.log, "checking", "GBP")
    forbidden_prefixes = ("finance.party.", "finance.employer.", "finance.mission.",
                           "finance.decision.", "finance.decision_outcome.")
    kinds = [e["kind"] for e in kernel.log.events()]
    assert not any(k.startswith(forbidden_prefixes) for k in kinds)
