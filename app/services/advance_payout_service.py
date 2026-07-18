"""
Advance Payout Service.

Business rule (from assignment):
- Every Pending sale is eligible for an advance payout of 10% of its earnings.
- Once an advance payout has been successfully transferred for a sale, that
  sale must never receive another advance payout, even if this job runs
  multiple times.

Idempotency strategy:
Each Sale row has an `advance_paid` amount (defaults to 0). Before paying an
advance on a sale, we check `advance_paid == 0`. If it's already non-zero,
we skip it. This makes the job safe to re-run at any time — e.g. via a
scheduled cron job — without double-paying.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.sale import Sale, SaleStatus
from app.models.user import User
from app.models.payout import Payout, PayoutType, PayoutStatus
from app.schemas.payout import AdvancePayoutResult
from app.utils.exceptions import UserNotFoundError


def run_advance_payout_for_user(db: Session, user_id: str) -> AdvancePayoutResult:
    """
    Runs the advance payout job for a single user.

    Finds all of the user's Pending sales, pays a 10% advance on any that
    haven't already received one, and returns a summary of what happened.
    Safe to call repeatedly — already-advanced sales are skipped, not
    re-paid.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise UserNotFoundError(f"User '{user_id}' not found")

    pending_sales = (
        db.query(Sale)
        .filter(Sale.user_id == user.id, Sale.status == SaleStatus.PENDING)
        .all()
    )

    advance_percentage = Decimal(str(settings.ADVANCE_PAYOUT_PERCENTAGE)) / Decimal("100")

    sales_paid: list[int] = []
    sales_skipped: list[int] = []
    total_advance_paid = Decimal("0")

    for sale in pending_sales:
        # Idempotency check — this is what prevents double-paying if the
        # job is triggered more than once for the same sale.
        if sale.advance_paid and Decimal(str(sale.advance_paid)) > 0:
            sales_skipped.append(sale.id)
            continue

        advance_amount = Decimal(str(sale.earning)) * advance_percentage

        sale.advance_paid = advance_amount
        user.withdrawable_balance = Decimal(str(user.withdrawable_balance)) + advance_amount

        payout_record = Payout(
            user_id=user.id,
            sale_id=sale.id,
            payout_type=PayoutType.ADVANCE,
            status=PayoutStatus.COMPLETED,
            amount=advance_amount,
        )
        db.add(payout_record)

        sales_paid.append(sale.id)
        total_advance_paid += advance_amount

    db.commit()

    return AdvancePayoutResult(
        user_id=user.user_id,
        total_advance_paid=float(total_advance_paid),
        sales_paid=sales_paid,
        sales_skipped=sales_skipped,
    )


def run_advance_payout_for_all_users(db: Session) -> list[AdvancePayoutResult]:
    """
    Convenience wrapper to run the advance payout job across every user —
    useful for simulating a scheduled batch job that processes all pending
    sales system-wide.
    """
    users = db.query(User).all()
    return [run_advance_payout_for_user(db, user.user_id) for user in users]
