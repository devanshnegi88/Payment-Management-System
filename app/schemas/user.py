"""
Pydantic schemas for User — creation and response contracts.
"""

from datetime import datetime

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Used to create a new user."""

    user_id: str = Field(..., description="String user identifier, e.g. 'john_doe'")
    name: str = Field(..., description="Display name for the user")


class UserResponse(BaseModel):
    """What we return to API consumers for a single user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    withdrawable_balance: float
    last_withdrawal_at: datetime | None = None
    created_at: datetime


class WithdrawalRequest(BaseModel):
    """
    Empty body for now — a withdrawal always withdraws the full
    withdrawable_balance. Kept as an explicit schema (rather than no body
    at all) so it's easy to extend later, e.g. if partial withdrawals are
    ever supported.
    """
    pass


class WithdrawalResponse(BaseModel):
    """Result of a successful withdrawal."""

    user_id: str
    amount_withdrawn: float
    withdrawn_at: datetime
    next_withdrawal_available_at: datetime
