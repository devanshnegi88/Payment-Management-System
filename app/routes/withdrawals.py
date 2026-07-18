"""
Withdrawals routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import WithdrawalResponse
from app.services.withdrawal_service import withdraw
from app.utils.exceptions import (
    UserNotFoundError,
    WithdrawalCooldownError,
    InsufficientBalanceError,
)

router = APIRouter(prefix="/withdrawals", tags=["Withdrawals"])


@router.post("/{user_id}", response_model=WithdrawalResponse)
def withdraw_funds(user_id: str, db: Session = Depends(get_db)):
    """
    Withdraws a user's full withdrawable balance, subject to the 24-hour
    cooldown between withdrawals.
    """
    try:
        return withdraw(db, user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WithdrawalCooldownError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
