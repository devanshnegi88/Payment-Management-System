"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-18

Creates the three core tables: users, sales, payouts — along with the
Postgres enum types for sale status and payout type/status.
"""
from typing import Sequence, Union

from alembic import op
# pyrefly: ignore [missing-import]
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL to sidestep SQLAlchemy's automatic _on_table_create enum
    # hooks, which fire even with create_type=False and cause DuplicateObject
    # errors when enum types already exist from a partial previous run.

    # PostgreSQL has no "CREATE TYPE IF NOT EXISTS" syntax.
    # Use DO blocks that swallow the duplicate_object exception instead —
    # this is the standard idempotent pattern for enum creation.
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sale_status AS ENUM ('pending', 'approved', 'rejected');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payout_type AS ENUM ('advance', 'final', 'withdrawal');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payout_status AS ENUM ('pending', 'completed', 'failed', 'cancelled', 'rejected');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            user_id     VARCHAR(100) NOT NULL,
            name        VARCHAR(255) NOT NULL,
            withdrawable_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
            last_withdrawal_at   TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_user_id ON users (user_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            brand         VARCHAR(100) NOT NULL,
            status        sale_status NOT NULL DEFAULT 'pending',
            earning       NUMERIC(12,2) NOT NULL,
            advance_paid  NUMERIC(12,2) NOT NULL DEFAULT 0,
            is_reconciled BOOLEAN NOT NULL DEFAULT false,
            created_at    TIMESTAMPTZ NOT NULL,
            reconciled_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_user_id ON sales (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_status  ON sales (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS payouts (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            sale_id      INTEGER REFERENCES sales(id),
            payout_type  payout_type   NOT NULL,
            status       payout_status NOT NULL DEFAULT 'completed',
            amount       NUMERIC(12,2) NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL,
            recovered_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_user_id     ON payouts (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_sale_id     ON payouts (sale_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_payout_type ON payouts (payout_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payouts_status      ON payouts (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payouts")
    op.execute("DROP TABLE IF EXISTS sales")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS payout_status")
    op.execute("DROP TYPE IF EXISTS payout_type")
    op.execute("DROP TYPE IF EXISTS sale_status")
