"""
Tests for recovery_service — covers Question 2: crediting failed/cancelled/
rejected payouts back to the user's withdrawable balance, and ensuring
recovery never double-credits.
"""

from decimal import Decimal

from app.models.payout import Payout, PayoutType, PayoutStatus
from app.services.recovery_service import (
    update_payout_status,
    recover_unrecovered_failed_payouts,
)


def _make_withdrawal_payout(db, user, amount: float, status: PayoutStatus = PayoutStatus.COMPLETED):
    payout = Payout(
        user_id=user.id,
        sale_id=None,
        payout_type=PayoutType.WITHDRAWAL,
        status=status,
        amount=Decimal(str(amount)),
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


def test_failed_payout_credits_amount_back_to_balance(db, make_user):
    user = make_user()
    payout = _make_withdrawal_payout(db, user, amount=68.0)

    update_payout_status(db, payout.id, PayoutStatus.FAILED)

    db.refresh(user)
    assert float(user.withdrawable_balance) == 68.0


def test_rejected_and_cancelled_payouts_also_get_recovered(db, make_user):
    user = make_user()
    rejected = _make_withdrawal_payout(db, user, amount=10.0)
    cancelled = _make_withdrawal_payout(db, user, amount=15.0)

    update_payout_status(db, rejected.id, PayoutStatus.REJECTED)
    update_payout_status(db, cancelled.id, PayoutStatus.CANCELLED)

    db.refresh(user)
    assert float(user.withdrawable_balance) == 25.0


def test_recovery_is_idempotent_does_not_double_credit(db, make_user):
    user = make_user()
    payout = _make_withdrawal_payout(db, user, amount=68.0)

    update_payout_status(db, payout.id, PayoutStatus.FAILED)
    # Simulate the same "failed" callback being delivered a second time.
    update_payout_status(db, payout.id, PayoutStatus.FAILED)

    db.refresh(user)
    assert float(user.withdrawable_balance) == 68.0  # not 136.0


def test_recovery_sweep_recovers_missed_failed_payouts(db, make_user):
    """
    Simulates a payout that was already marked FAILED in the DB (e.g. from
    a missed webhook) but never actually recovered — the sweep should
    catch it.
    """
    user = make_user()
    payout = _make_withdrawal_payout(db, user, amount=30.0, status=PayoutStatus.FAILED)
    # Note: recovered_at is None since this bypassed update_payout_status.

    recovered = recover_unrecovered_failed_payouts(db, user.user_id)

    assert len(recovered) == 1
    db.refresh(user)
    assert float(user.withdrawable_balance) == 30.0


def test_recovery_sweep_skips_already_recovered_payouts(db, make_user):
    user = make_user()
    payout = _make_withdrawal_payout(db, user, amount=30.0)
    update_payout_status(db, payout.id, PayoutStatus.FAILED)  # recovered here

    recovered_again = recover_unrecovered_failed_payouts(db, user.user_id)

    assert len(recovered_again) == 0
    db.refresh(user)
    assert float(user.withdrawable_balance) == 30.0  # unchanged, not doubled
