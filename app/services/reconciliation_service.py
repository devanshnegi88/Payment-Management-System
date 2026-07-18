"""
Reconciliation Service.

Business rule (from assignment):
When an admin reconciles a Pending sale to Approved or Rejected, the final
payout is calculated by accounting for any advance already paid:

- Approved: final = earning - advance_paid
- Rejected: final = -advance_paid (a clawback, since the user was never
  entitled to the advance on a sale that didn't go through)

Idempotency strategy:
Each Sale has an `is_reconciled` flag. A sale can only be reconciled once —
this prevents the same sale's final adjustment from being applied twice if
the endpoint is called more than once by accident.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.sale import Sale, SaleStatus
from app.models.user import User
from app.models.payout import Payout, PayoutType, PayoutStatus
from app.schemas.payout import FinalPayoutResult
from app.utils.exceptions import (
    SaleNotFoundError,
    UserNotFoundError,
    InvalidReconciliationError,
)


def reconcile_sale(db: Session, sale_id: int, new_status: SaleStatus) -> dict:
    """
    Reconciles a single sale to Approved or Rejected, computes its final
    payout adjustment, credits the user's withdrawable_balance, and records
    a FINAL Payout entry.

    Returns a breakdown dict: {sale_id, status, earning, advance_paid, adjustment}
    """
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale is None:
        raise SaleNotFoundError(f"Sale with id {sale_id} not found")

    if new_status not in (SaleStatus.APPROVED, SaleStatus.REJECTED):
        raise InvalidReconciliationError(
            "A sale can only be reconciled to 'approved' or 'rejected'"
        )

    if sale.status != SaleStatus.PENDING:
        raise InvalidReconciliationError(
            f"Sale {sale_id} is not pending (current status: {sale.status.value}); "
            "only pending sales can be reconciled"
        )

    if sale.is_reconciled:
        # Defensive check — should be unreachable given the status check
        # above, but kept explicit since is_reconciled is the true source
        # of idempotency truth for this operation.
        raise InvalidReconciliationError(f"Sale {sale_id} has already been reconciled")

    earning = Decimal(str(sale.earning))
    advance_paid = Decimal(str(sale.advance_paid))

    if new_status == SaleStatus.APPROVED:
        adjustment = earning - advance_paid
    else:  # REJECTED
        adjustment = -advance_paid

    sale.status = new_status
    sale.is_reconciled = True
    sale.reconciled_at = datetime.now(timezone.utc)

    user = db.query(User).filter(User.id == sale.user_id).first()
    if user is None:
        raise UserNotFoundError(f"User for sale {sale_id} not found")

    user.withdrawable_balance = Decimal(str(user.withdrawable_balance)) + adjustment

    payout_record = Payout(
        user_id=user.id,
        sale_id=sale.id,
        payout_type=PayoutType.FINAL,
        status=PayoutStatus.COMPLETED,
        amount=adjustment,
    )
    db.add(payout_record)
    db.commit()

    return {
        "sale_id": sale.id,
        "status": new_status.value,
        "earning": float(earning),
        "advance_paid": float(advance_paid),
        "adjustment": float(adjustment),
    }


def reconcile_sales_batch(
    db: Session, user_id: str, reconciliations: list[dict]
) -> FinalPayoutResult:
    """
    Reconciles multiple sales for a user in one call and returns an
    aggregated summary — mirrors the "Example" walkthrough in the
    assignment (three sales reconciled together, one net final payout).

    `reconciliations` is a list of {"sale_id": int, "status": SaleStatus}.
    Each sale is reconciled independently via reconcile_sale, so a failure
    on one sale (e.g. already reconciled) doesn't roll back the others that
    already succeeded in this batch.
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise UserNotFoundError(f"User '{user_id}' not found")

    breakdown: list[dict] = []
    total_final_payout = Decimal("0")

    for item in reconciliations:
        result = reconcile_sale(db, item["sale_id"], item["status"])
        breakdown.append(result)
        total_final_payout += Decimal(str(result["adjustment"]))

    return FinalPayoutResult(
        user_id=user_id,
        total_final_payout=float(total_final_payout),
        breakdown=breakdown,
    )
