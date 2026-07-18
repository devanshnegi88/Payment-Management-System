"""
Sales routes.

Note on users: the assignment's reference data has sales carrying a raw
userId string with no separate user-creation step. To keep the API
surface simple (and match that reference data shape), creating a sale for
a userId that doesn't exist yet automatically creates a minimal User
record. This avoids requiring a separate "create user" endpoint just to
exercise the payout flows.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sale import Sale, SaleStatus
from app.models.user import User
from app.schemas.sale import SaleCreate, SaleResponse, SaleReconcileRequest
from app.schemas.payout import FinalPayoutResult
from app.services.reconciliation_service import reconcile_sale, reconcile_sales_batch
from app.utils.exceptions import SaleNotFoundError, InvalidReconciliationError, UserNotFoundError

router = APIRouter(prefix="/sales", tags=["Sales"])


class BatchReconciliationItem(BaseModel):
    sale_id: int
    status: SaleStatus


class BatchReconciliationRequest(BaseModel):
    user_id: str
    reconciliations: list[BatchReconciliationItem]


def _get_or_create_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        user = User(user_id=user_id, name=user_id)
        db.add(user)
        db.flush()  # assigns user.id without committing yet
    return user


def _to_sale_response(sale: Sale) -> SaleResponse:
    # Constructed explicitly (not via from_attributes) because
    # SaleResponse.user_id is the external string ID, while Sale.user_id
    # on the ORM model is the internal integer FK — see schemas/sale.py.
    return SaleResponse(
        id=sale.id,
        user_id=sale.user.user_id,
        brand=sale.brand,
        status=sale.status,
        earning=float(sale.earning),
        advance_paid=float(sale.advance_paid),
        is_reconciled=sale.is_reconciled,
        created_at=sale.created_at,
        reconciled_at=sale.reconciled_at,
    )


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    """Creates a new sale (always starts as Pending), auto-creating the user if needed."""
    user = _get_or_create_user(db, payload.user_id)

    sale = Sale(
        user_id=user.id,
        brand=payload.brand,
        earning=payload.earning,
        status=SaleStatus.PENDING,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    return _to_sale_response(sale)


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    """Fetches a single sale by ID."""
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return _to_sale_response(sale)


@router.get("", response_model=list[SaleResponse])
def list_sales(user_id: str, db: Session = Depends(get_db)):
    """Lists all sales for a given user (userId query param)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    sales = db.query(Sale).filter(Sale.user_id == user.id).all()
    return [_to_sale_response(sale) for sale in sales]


@router.patch("/{sale_id}/reconcile", response_model=SaleResponse)
def reconcile_single_sale(
    sale_id: int, payload: SaleReconcileRequest, db: Session = Depends(get_db)
):
    """
    Admin endpoint: reconciles a single sale to Approved or Rejected,
    computing and applying its final payout adjustment.
    """
    try:
        reconcile_sale(db, sale_id, payload.status)
    except SaleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidReconciliationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    return _to_sale_response(sale)


@router.post("/reconcile/batch", response_model=FinalPayoutResult)
def reconcile_multiple_sales(payload: BatchReconciliationRequest, db: Session = Depends(get_db)):
    """
    Admin endpoint: reconciles multiple sales for one user in a single call
    and returns the aggregated final payout — mirrors the assignment's
    multi-sale "Example" walkthrough.
    """
    reconciliations = [
        {"sale_id": item.sale_id, "status": item.status} for item in payload.reconciliations
    ]
    try:
        return reconcile_sales_batch(db, payload.user_id, reconciliations)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SaleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidReconciliationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
