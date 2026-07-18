"""
Shared pytest fixtures.

Tests run against an in-memory SQLite database rather than a live
PostgreSQL instance — this keeps the test suite fast and dependency-free
(no need to spin up Postgres just to run unit tests), while still
exercising the exact same SQLAlchemy models and service-layer logic that
run in production. SQLite supports everything our models use (Enum,
Numeric, DateTime, ForeignKey), so behavior is equivalent for these tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.user import User
from app.models.sale import Sale, SaleStatus


@pytest.fixture()
def db() -> Session:
    """Provides a fresh, isolated in-memory database session per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def make_user(db: Session):
    """Factory fixture for creating a User in the test DB."""

    def _make_user(user_id: str = "john_doe", name: str = "John Doe") -> User:
        user = User(user_id=user_id, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture()
def make_sale(db: Session):
    """Factory fixture for creating a Sale in the test DB."""

    def _make_sale(
        user: User,
        earning: float = 40.0,
        brand: str = "brand_1",
        status: SaleStatus = SaleStatus.PENDING,
    ) -> Sale:
        sale = Sale(user_id=user.id, brand=brand, earning=earning, status=status)
        db.add(sale)
        db.commit()
        db.refresh(sale)
        return sale

    return _make_sale
