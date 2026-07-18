"""
Payouts routes.

Covers:
- Triggering the advance payout job (single user or all users)
- Listing a user's payout history
- Simulating a payment processor status callback (Question 2 entry point)
- Manually triggering the recovery sweep
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.payout import Payout, PayoutStatus
from app.schemas.payout import AdvancePayoutResult, PayoutResponse
from app.services.advance_payout_service import (
    run_advance_payout_for_user,
    run_advance_payout_for_all_users,
)
from app.services.recovery_service import update_payout_status, recover_unrecovered_failed_payouts
from app.utils.exceptions import UserNotFoundError, PayoutNotFoundError, InvalidPayoutTransitionError

router = APIRouter(prefix="/payouts", tags=["Payouts"])


class PayoutStatusUpdateRequest(BaseModel):
    status: PayoutStatus


@router.post("/advance/{user_id}", response_model=AdvancePayoutResult)
def trigger_advance_payout(user_id: str, db: Session = Depends(get_db)):
    """
    Runs the advance payout job for a single user. Safe to call repeatedly —
    sales that already received an advance are skipped, not re-paid.
    """
    try:
        return run_advance_payout_for_user(db, user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/advance", response_model=list[AdvancePayoutResult])
def trigger_advance_payout_all_users(db: Session = Depends(get_db)):
    """
    Runs the advance payout job across every user in the system — simulates
    a scheduled batch job.
    """
    return run_advance_payout_for_all_users(db)


@router.get("", response_model=list[PayoutResponse])
def list_payouts(user_id: str, db: Session = Depends(get_db)):
    """Lists the full payout ledger (advance, final, withdrawal) for a user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payouts = db.query(Payout).filter(Payout.user_id == user.id).all()
    return [PayoutResponse.model_validate(p) for p in payouts]


@router.patch("/{payout_id}/status", response_model=PayoutResponse)
def update_payout_status_endpoint(
    payout_id: int, payload: PayoutStatusUpdateRequest, db: Session = Depends(get_db)
):
    """
    Simulates a payment processor callback updating a payout's status.
    If the new status is Failed/Cancelled/Rejected, the amount is
    automatically credited back to the user's withdrawable balance
    (Question 2).
    """
    try:
        return update_payout_status(db, payout_id, payload.status)
    except PayoutNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidPayoutTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/recover/{user_id}", response_model=list[PayoutResponse])
def trigger_recovery_sweep(user_id: str, db: Session = Depends(get_db)):
    """
    Defensive batch sweep: recovers any of the user's Failed/Cancelled/
    Rejected payouts that were never credited back (e.g. a missed
    callback). Safe to call repeatedly — already-recovered payouts are
    skipped.
    """
    return recover_unrecovered_failed_payouts(db, user_id)
