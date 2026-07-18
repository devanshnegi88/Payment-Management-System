"""
Tests for advance_payout_service — covers the 10% advance calculation and,
critically, the idempotency guarantee: running the job twice must never
double-pay the same sale.
"""

from app.models.sale import SaleStatus
from app.models.payout import PayoutType
from app.services.advance_payout_service import run_advance_payout_for_user


def test_advance_payout_pays_ten_percent_of_pending_earning(db, make_user, make_sale):
    user = make_user()
    make_sale(user, earning=40.0)  # matches assignment reference data

    result = run_advance_payout_for_user(db, user.user_id)

    assert result.total_advance_paid == 4.0
    assert len(result.sales_paid) == 1
    assert len(result.sales_skipped) == 0


def test_advance_payout_matches_assignment_example(db, make_user, make_sale):
    """
    Reproduces the assignment's worked example: three pending sales of ₹40
    each => total pending earnings ₹120 => 10% advance => ₹12.
    """
    user = make_user()
    make_sale(user, earning=40.0)
    make_sale(user, earning=40.0)
    make_sale(user, earning=40.0)

    result = run_advance_payout_for_user(db, user.user_id)

    assert result.total_advance_paid == 12.0
    assert len(result.sales_paid) == 3


def test_advance_payout_is_idempotent_on_rerun(db, make_user, make_sale):
    """
    Core business rule: once a sale has received an advance, running the
    job again must skip it entirely, not pay it a second time.
    """
    user = make_user()
    make_sale(user, earning=40.0)

    first_run = run_advance_payout_for_user(db, user.user_id)
    second_run = run_advance_payout_for_user(db, user.user_id)

    assert first_run.total_advance_paid == 4.0
    assert second_run.total_advance_paid == 0.0
    assert len(second_run.sales_paid) == 0
    assert len(second_run.sales_skipped) == 1

    # The user's balance should reflect only ONE advance payout, not two.
    db.refresh(user)
    assert float(user.withdrawable_balance) == 4.0

    # And only one ADVANCE payout ledger entry should exist for the sale.
    from app.models.payout import Payout

    advance_payouts = (
        db.query(Payout)
        .filter(Payout.user_id == user.id, Payout.payout_type == PayoutType.ADVANCE)
        .all()
    )
    assert len(advance_payouts) == 1


def test_advance_payout_ignores_non_pending_sales(db, make_user, make_sale):
    """Only Pending sales are eligible for an advance payout."""
    user = make_user()
    make_sale(user, earning=40.0, status=SaleStatus.APPROVED)

    result = run_advance_payout_for_user(db, user.user_id)

    assert result.total_advance_paid == 0.0
    assert len(result.sales_paid) == 0


def test_advance_payout_raises_for_unknown_user(db):
    from app.utils.exceptions import UserNotFoundError
    import pytest

    with pytest.raises(UserNotFoundError):
        run_advance_payout_for_user(db, "nonexistent_user")
