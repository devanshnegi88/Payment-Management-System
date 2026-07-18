"""
Payout model.

Represents a single payout event in the system. This is deliberately a
general-purpose ledger entry rather than three separate tables, because
advance payouts, final payouts, and withdrawals all share the same shape:
an amount, tied to a user, with a lifecycle status.

Keeping them in one table also makes Question 2 (failed payout recovery)
straightforward — recovery just looks for Payout rows in a bad terminal
state and credits their amount back to the user.
"""

import enum
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
from sqlalchemy import Numeric, DateTime, ForeignKey, Enum as SqlEnum
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PayoutType(str, enum.Enum):
    ADVANCE = "advance"        # 10% advance paid on a pending sale
    FINAL = "final"            # Final adjustment after reconciliation
    WITHDRAWAL = "withdrawal"  # User cashing out their withdrawable_balance


class PayoutStatus(str, enum.Enum):
    PENDING = "pending"        # Initiated but not yet confirmed
    COMPLETED = "completed"    # Successfully transferred
    FAILED = "failed"          # Transfer failed (e.g. bank error)
    CANCELLED = "cancelled"    # Cancelled before completion
    REJECTED = "rejected"      # Rejected by payment processor


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Nullable because WITHDRAWAL payouts aren't tied to a single sale —
    # they draw from the user's aggregated withdrawable_balance.
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), nullable=True, index=True)

    payout_type: Mapped[PayoutType] = mapped_column(
        SqlEnum(
            PayoutType,
            name="payout_type",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[PayoutStatus] = mapped_column(
        SqlEnum(
            PayoutStatus,
            name="payout_status",
            values_callable=lambda e: [x.value for x in e],
            native_enum=False,
        ),
        default=PayoutStatus.COMPLETED,
        nullable=False,
        index=True,
    )

    # Positive for money paid out, negative for a clawback adjustment
    # (e.g. a FINAL payout on a rejected sale is negative — see
    # reconciliation_service.py).
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Set only when a failed/cancelled/rejected payout's amount has been
    # credited back to the user's withdrawable_balance, so recovery never
    # processes the same failed payout twice.
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="payouts")
    sale: Mapped["Sale | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Payout id={self.id} type={self.payout_type} status={self.status} amount={self.amount}>"
