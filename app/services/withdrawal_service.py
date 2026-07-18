"""
Withdrawal Service.

Business rule (from assignment):
A user can make only one payout withdrawal every 24 hours.

Enforcement strategy:
User.last_withdrawal_at stores the timestamp of the last successful
withdrawal. Before allowing a new withdrawal, we check whether
(now - last_withdrawal_at) >= WITHDRAWAL_COOLDOWN_HOURS. This is a simple,
reliable check that doesn't require a separate rate-limiting table.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.payout import Payout, PayoutType, PayoutStatus
from app.schemas.user import WithdrawalResponse
from app.utils.exceptions import (
    UserNotFoundError,
    WithdrawalCooldownError,
    InsufficientBalanceError,
)


def withdraw(db: Session, user_id: str) -> WithdrawalResponse:
    """
    Withdraws the user's full withdrawable_balance, subject to the 24-hour
    cooldown rule. Raises WithdrawalCooldownError if the user withdrew too
    recently, or InsufficientBalanceError if there's nothing to withdraw.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise UserNotFoundError(f"User '{user_id}' not found")

    now = datetime.now(timezone.utc)
    cooldown = timedelta(hours=settings.WITHDRAWAL_COOLDOWN_HOURS)

    if user.last_withdrawal_at is not None:
        # last_withdrawal_at is stored timezone-aware; guard against naive
        # datetimes just in case the DB driver returns one.
        last_withdrawal = user.last_withdrawal_at
        if last_withdrawal.tzinfo is None:
            last_withdrawal = last_withdrawal.replace(tzinfo=timezone.utc)

        next_available_at = last_withdrawal + cooldown
        if now < next_available_at:
            raise WithdrawalCooldownError(
                f"User '{user_id}' cannot withdraw again until {next_available_at.isoformat()}"
            )

    balance = Decimal(str(user.withdrawable_balance))
    if balance <= 0:
        raise InsufficientBalanceError(f"User '{user_id}' has no withdrawable balance")

    # Record the withdrawal as a negative-balance-impact ledger entry.
    payout_record = Payout(
        user_id=user.id,
        sale_id=None,
        payout_type=PayoutType.WITHDRAWAL,
        status=PayoutStatus.COMPLETED,
        amount=balance,
    )
    db.add(payout_record)

    user.withdrawable_balance = Decimal("0")
    user.last_withdrawal_at = now
    db.commit()

    return WithdrawalResponse(
        user_id=user.user_id,
        amount_withdrawn=float(balance),
        withdrawn_at=now,
        next_withdrawal_available_at=now + cooldown,
    )
