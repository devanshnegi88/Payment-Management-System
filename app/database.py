"""
Database setup: SQLAlchemy engine, session factory, and declarative base.

Note: This file imports `settings` from app.config, which is generated in the
next step. This is expected — database.py depends on config.py for the
DATABASE_URL, but is listed first in the build order since it's the more
foundational piece conceptually (the config module exists purely to serve it).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import settings

# The engine manages the actual connection pool to PostgreSQL.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verifies connections are alive before using them,
                         # avoids errors from stale/dropped DB connections.
)

# SessionLocal is a factory for creating new database sessions.
# autocommit=False and autoflush=False give us explicit control over
# when changes are flushed/committed — important for payout transactions
# where we want atomic writes (e.g. sale update + payout record together).
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class that all ORM models will inherit from.
Base = declarative_base()


def get_db() -> Session:
    """
    FastAPI dependency that provides a database session per request.

    Ensures the session is always closed after the request finishes,
    even if an error occurs, preventing connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
