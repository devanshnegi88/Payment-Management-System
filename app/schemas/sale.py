"""
Pydantic schemas for Sale — request/response contracts, kept separate from
the SQLAlchemy model so API consumers never see internal-only fields
(like is_reconciled) unless we explicitly choose to expose them.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sale import SaleStatus


class SaleCreate(BaseModel):
    """Used when seeding/creating a new sale (always starts as pending)."""

    user_id: str = Field(..., description="String user identifier, e.g. 'john_doe'")
    brand: str = Field(..., description="Brand name, e.g. 'brand_1'")
    earning: float = Field(..., gt=0, description="Earning amount for this sale, must be positive")


class SaleReconcileRequest(BaseModel):
    """Used by the admin endpoint to reconcile a sale's status."""

    status: SaleStatus = Field(
        ..., description="New status for the sale. Must be 'approved' or 'rejected'."
    )


class SaleResponse(BaseModel):
    """What we return to API consumers for a single sale."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str = Field(..., description="Populated from the related User's user_id")
    brand: str
    status: SaleStatus
    earning: float
    advance_paid: float
    is_reconciled: bool
    created_at: datetime
    reconciled_at: datetime | None = None
