"""
Application entrypoint.

Registers all routers and a global exception handler that catches any
DomainError not already handled explicitly within a route (defensive
fallback — routes catch specific exceptions individually for precise HTTP
status codes, but this ensures nothing leaks out as an unhandled 500).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base
from app.utils.exceptions import DomainError
from app.routes import sales, payouts, withdrawals
import app.models  # noqa: F401 — registers all ORM models before create_all

app = FastAPI(
    title=settings.APP_NAME,
    description="Manages advance and final payouts for affiliate sales.",
    version="1.0.0",
    debug=settings.DEBUG,
)

app.include_router(sales.router)
app.include_router(payouts.router)
app.include_router(withdrawals.router)


@app.on_event("startup")
def create_tables() -> None:
    """
    Create all tables on startup if they don't exist yet.
    This is a safety net for when Alembic migrations are in an inconsistent
    state (version recorded but tables missing). SQLAlchemy's create_all uses
    checkfirst=True internally, so it's safe to call on every boot.
    """
    Base.metadata.create_all(bind=engine)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """
    Defensive fallback for any DomainError that a route didn't explicitly
    catch and translate. Returns 400 by default, since almost all
    DomainError subclasses represent a business-rule violation rather than
    a server fault.
    """
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", tags=["Health"])
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "app_name": settings.APP_NAME}
