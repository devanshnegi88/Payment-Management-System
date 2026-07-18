"""
Failed Payout Recovery Service (Question 2).

Business rule (from assignment):
If a payout initiated to the user is later Cancelled, Rejected, or Failed,
the system should credit that amount back into the user's withdrawable
balance, and allow the user to initiate another withdrawal for it.

Design:
- `update_payout_status()` simulates a payment processor callback (e.g. a
  webhook) informing us that a previously-initiated payout has moved to a
  terminal bad state. As soon as that happens, we credit the amount back
  immediately — no separate polling job needed.
- `recovered_at` on the Payout row makes this idempotent: if the same
  "failed" callback were somehow delivered twice, the second call is a
  no-op instead of double-crediting the user.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.payout import Payout, PayoutStatus
from app.models.user import User
from app.schemas.payout import PayoutResponse
from app.utils.exceptions import PayoutNotFoundError, InvalidPayoutTransitionError

# Statuses that indicate a payout did not actually succeed, and therefore
# should be credited back to the user's withdrawable balance.
RECOVERABLE_STATUSES = {PayoutStatus.FAILED, PayoutStatus.CANCELLED, PayoutStatus.REJECTED}


def update_payout_status(db: Session, payout_id: int, new_status: PayoutStatus) -> PayoutResponse:
    """
    Updates a payout's status (simulating a processor callback). If the new
    status is Failed/Cancelled/Rejected, automatically credits the payout
    amount back to the user's withdrawable_balance.
    """
    payout = db.query(Payout).filter(Payout.id == payout_id).first()
    if payout is None:
        raise PayoutNotFoundError(f"Payout with id {payout_id} not found")

    if payout.status == PayoutStatus.COMPLETED and new_status == PayoutStatus.COMPLETED:
        raise InvalidPayoutTransitionError(f"Payout {payout_id} is already completed")

    payout.status = new_status

    if new_status in RECOVERABLE_STATUSES and payout.recovered_at is None:
        user = db.query(User).filter(User.id == payout.user_id).first()
        if user is not None:
            # Recovering means giving the user back the amount they didn't
            # actually receive, so it becomes withdrawable again.
            user.withdrawable_balance = Decimal(str(user.withdrawable_balance)) + Decimal(
                str(abs(payout.amount))
            )
            payout.recovered_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(payout)
    return PayoutResponse.model_validate(payout)


def recover_unrecovered_failed_payouts(db: Session, user_id: str) -> list[PayoutResponse]:
    """
    Batch safety-net: finds any of the user's payouts that are already in a
    Failed/Cancelled/Rejected state but were never credited back (e.g. due
    to a bug or a missed callback), and recovers them now.

    This is idempotent — running it repeatedly only ever recovers each
    payout once, thanks to the recovered_at check.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        return []

    unrecovered = (
        db.query(Payout)
        .filter(
            Payout.user_id == user.id,
            Payout.status.in_(RECOVERABLE_STATUSES),
            Payout.recovered_at.is_(None),
        )
        .all()
    )

    recovered: list[PayoutResponse] = []
    for payout in unrecovered:
        user.withdrawable_balance = Decimal(str(user.withdrawable_balance)) + Decimal(
            str(abs(payout.amount))
        )
        payout.recovered_at = datetime.now(timezone.utc)
        recovered.append(payout)

    db.commit()
    for payout in recovered:
        db.refresh(payout)

    return [PayoutResponse.model_validate(p) for p in recovered]
