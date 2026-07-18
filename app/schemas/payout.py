"""
Pydantic schemas for Payout — covers advance payout summaries, final payout
summaries (reconciliation results), and individual payout ledger entries.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.payout import PayoutType, PayoutStatus


class PayoutResponse(BaseModel):
    """A single payout ledger entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_id: int | None
    payout_type: PayoutType
    status: PayoutStatus
    amount: float
    created_at: datetime
    recovered_at: datetime | None = None


class AdvancePayoutResult(BaseModel):
    """
    Summary returned after running the advance payout job for a user.
    Distinguishes newly-paid sales from ones skipped because they'd
    already received an advance (demonstrates the idempotency explicitly
    in the API response, not just internally).
    """

    user_id: str
    total_advance_paid: float = Field(..., description="Sum of advance paid in this run")
    sales_paid: list[int] = Field(..., description="IDs of sales that received an advance this run")
    sales_skipped: list[int] = Field(
        ..., description="IDs of pending sales skipped because they were already advanced"
    )


class FinalPayoutResult(BaseModel):
    """Summary returned after reconciling and computing final payout for a user."""

    user_id: str
    total_final_payout: float = Field(
        ..., description="Net final payout across all newly reconciled sales in this run"
    )
    breakdown: list[dict] = Field(
        ..., description="Per-sale breakdown: sale_id, status, earning, advance_paid, adjustment"
    )
