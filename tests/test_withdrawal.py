"""
Tests for withdrawal_service — covers the 24-hour cooldown restriction,
insufficient balance handling, and successful withdrawal behavior.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.withdrawal_service import withdraw
from app.utils.exceptions import (
    UserNotFoundError,
    WithdrawalCooldownError,
    InsufficientBalanceError,
)


def _give_balance(db, user, amount: float):
    """Test helper: directly credits a user's withdrawable balance."""
    user.withdrawable_balance = Decimal(str(amount))
    db.commit()
    db.refresh(user)


def test_withdraw_success_transfers_full_balance(db, make_user):
    user = make_user()
    _give_balance(db, user, 68.0)

    result = withdraw(db, user.user_id)

    assert result.amount_withdrawn == 68.0

    db.refresh(user)
    assert float(user.withdrawable_balance) == 0.0
    assert user.last_withdrawal_at is not None


def test_withdraw_raises_when_balance_is_zero(db, make_user):
    user = make_user()  # balance defaults to 0

    with pytest.raises(InsufficientBalanceError):
        withdraw(db, user.user_id)


def test_withdraw_raises_cooldown_error_if_too_soon(db, make_user):
    user = make_user()
    _give_balance(db, user, 50.0)

    withdraw(db, user.user_id)  # first withdrawal succeeds

    _give_balance(db, user, 20.0)  # simulate more earnings arriving

    with pytest.raises(WithdrawalCooldownError):
        withdraw(db, user.user_id)  # too soon since the last withdrawal


def test_withdraw_allowed_after_cooldown_period_elapses(db, make_user):
    user = make_user()
    _give_balance(db, user, 50.0)

    # Simulate a withdrawal that happened 25 hours ago (past the 24h cooldown).
    user.last_withdrawal_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db.commit()

    result = withdraw(db, user.user_id)

    assert result.amount_withdrawn == 50.0


def test_withdraw_raises_for_unknown_user(db):
    with pytest.raises(UserNotFoundError):
        withdraw(db, "nonexistent_user")
