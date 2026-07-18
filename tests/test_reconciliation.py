"""
Tests for reconciliation_service — covers the final payout calculation for
both Approved and Rejected sales, the multi-sale batch example from the
assignment, and reconciliation idempotency/validation.
"""

import pytest

from app.models.sale import SaleStatus
from app.services.advance_payout_service import run_advance_payout_for_user
from app.services.reconciliation_service import reconcile_sale, reconcile_sales_batch
from app.utils.exceptions import InvalidReconciliationError, UserNotFoundError


def test_approved_sale_final_payout_is_earning_minus_advance(db, make_user, make_sale):
    """Case 1 from the assignment: earning ₹30, advance ₹3 -> final ₹27."""
    user = make_user()
    sale = make_sale(user, earning=30.0)
    run_advance_payout_for_user(db, user.user_id)  # advance_paid becomes ₹3

    result = reconcile_sale(db, sale.id, SaleStatus.APPROVED)

    assert result["adjustment"] == 27.0
    assert result["status"] == "approved"


def test_rejected_sale_final_payout_is_negative_advance(db, make_user, make_sale):
    """Case 2 from the assignment: earning ₹50, advance ₹5 -> adjustment -₹5."""
    user = make_user()
    sale = make_sale(user, earning=50.0)
    run_advance_payout_for_user(db, user.user_id)  # advance_paid becomes ₹5

    result = reconcile_sale(db, sale.id, SaleStatus.REJECTED)

    assert result["adjustment"] == -5.0
    assert result["status"] == "rejected"


def test_reconciliation_updates_user_withdrawable_balance(db, make_user, make_sale):
    """
    After reconciliation, the user's withdrawable balance should reflect
    the advance already paid PLUS the final adjustment.
    e.g. advance ₹4 credited first, then final adjustment ₹36 credited
    on approval -> total balance ₹40 (the full earning, paid in two parts).
    """
    user = make_user()
    sale = make_sale(user, earning=40.0)
    run_advance_payout_for_user(db, user.user_id)  # balance = 4

    reconcile_sale(db, sale.id, SaleStatus.APPROVED)  # balance += 36

    db.refresh(user)
    assert float(user.withdrawable_balance) == 40.0


def test_assignment_worked_example_batch_reconciliation(db, make_user, make_sale):
    """
    Reproduces the assignment's full worked example:
    3 sales of ₹40 each, ₹4 advance each (total ₹12 advance paid).
    Reconciled as: rejected, approved, approved.
    Expected final payout: -4 + 36 + 36 = 68.
    """
    user = make_user()
    sale_1 = make_sale(user, earning=40.0)
    sale_2 = make_sale(user, earning=40.0)
    sale_3 = make_sale(user, earning=40.0)

    run_advance_payout_for_user(db, user.user_id)  # ₹4 advance on each sale

    result = reconcile_sales_batch(
        db,
        user.user_id,
        [
            {"sale_id": sale_1.id, "status": SaleStatus.REJECTED},
            {"sale_id": sale_2.id, "status": SaleStatus.APPROVED},
            {"sale_id": sale_3.id, "status": SaleStatus.APPROVED},
        ],
    )

    assert result.total_final_payout == 68.0
    assert len(result.breakdown) == 3


def test_cannot_reconcile_same_sale_twice(db, make_user, make_sale):
    """A sale that's already been reconciled cannot be reconciled again."""
    user = make_user()
    sale = make_sale(user, earning=40.0)
    run_advance_payout_for_user(db, user.user_id)

    reconcile_sale(db, sale.id, SaleStatus.APPROVED)

    with pytest.raises(InvalidReconciliationError):
        reconcile_sale(db, sale.id, SaleStatus.APPROVED)


def test_cannot_reconcile_sale_that_is_not_pending(db, make_user, make_sale):
    """Only Pending sales can be reconciled."""
    user = make_user()
    sale = make_sale(user, earning=40.0, status=SaleStatus.APPROVED)

    with pytest.raises(InvalidReconciliationError):
        reconcile_sale(db, sale.id, SaleStatus.REJECTED)


def test_reconcile_sales_batch_raises_for_unknown_user(db):
    with pytest.raises(UserNotFoundError):
        reconcile_sales_batch(db, "nonexistent_user", [])
