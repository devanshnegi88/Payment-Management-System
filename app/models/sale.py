"""
Sale model.

Represents a single affiliate sale. Tracks its reconciliation status and
whether/how much advance payout has already been paid on it — this is the
field that makes advance payouts idempotent (see advance_payout_service.py).
"""

import enum
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SqlEnum
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SaleStatus(str, enum.Enum):
    """
    Matches the three possible status values from the assignment.
    Using a Python enum (backed by a DB enum type) instead of a raw string
    prevents invalid status values from ever being persisted.
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    brand: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[SaleStatus] = mapped_column(
    SqlEnum(
        SaleStatus,
        name="sale_status",
        values_callable=lambda enum: [e.value for e in enum],
        native_enum=False,  # ensures .value (lowercase) is sent, not the member name
    ),
    default=SaleStatus.PENDING,
    nullable=False,
    index=True,
)

    earning: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # How much advance payout has been paid on this specific sale so far.
    # Starts at 0. Set to (earning * ADVANCE_PAYOUT_PERCENTAGE) the first
    # (and only) time the advance payout job processes this sale.
    #
    # This field — not a recalculation — is the single source of truth for
    # "has this sale already received an advance", which is what makes the
    # advance payout job safe to re-run without double-paying.
    advance_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Whether this sale has already been included in a final payout
    # calculation during reconciliation. Prevents the same sale from being
    # reconciled twice and double-counting its final adjustment.
    is_reconciled: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sales")

    def __repr__(self) -> str:
        return f"<Sale id={self.id} status={self.status} earning={self.earning}>"
