"""
User model.

Represents an affiliate/user who earns from sales and receives payouts.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Using a human-readable string ID (e.g. "john_doe") to match the
    # reference data in the assignment, in addition to the internal
    # numeric primary key.
    user_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Tracks funds available to withdraw right now. This is a running ledger
    # balance — it increases when final payouts are calculated or failed
    # payouts are recovered, and decreases when a withdrawal is made.
    #
    # Numeric(12, 2) is used instead of Float to avoid floating-point
    # rounding errors with currency values.
    withdrawable_balance: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    # Tracks the last time the user successfully withdrew, used to enforce
    # the 24-hour withdrawal cooldown. Nullable because a brand-new user
    # has never withdrawn yet.
    last_withdrawal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships — allows navigating from a User to their Sales/Payouts
    # in Python without writing manual joins.
    sales: Mapped[list["Sale"]] = relationship(back_populates="user")
    payouts: Mapped[list["Payout"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User user_id={self.user_id} balance={self.withdrawable_balance}>"
