"""
Custom exception classes for domain/business-rule errors.

Keeping these as plain Python exceptions (rather than raising HTTPException
directly inside services) keeps the services layer framework-agnostic —
services don't need to know about FastAPI/HTTP status codes at all. The
routes layer catches these and translates them into appropriate HTTP
responses.
"""


class DomainError(Exception):
    """Base class for all custom domain errors in this application."""
    pass


class UserNotFoundError(DomainError):
    """Raised when a referenced user does not exist."""
    pass


class SaleNotFoundError(DomainError):
    """Raised when a referenced sale does not exist."""
    pass


class PayoutNotFoundError(DomainError):
    """Raised when a referenced payout does not exist."""
    pass


class InvalidReconciliationError(DomainError):
    """
    Raised when a sale reconciliation is attempted that violates business
    rules — e.g. reconciling a non-pending sale, reconciling to an invalid
    status, or reconciling an already-reconciled sale.
    """
    pass


class WithdrawalCooldownError(DomainError):
    """Raised when a user attempts to withdraw before the 24-hour cooldown has elapsed."""
    pass


class InsufficientBalanceError(DomainError):
    """Raised when a user attempts to withdraw with a zero or negative withdrawable balance."""
    pass


class InvalidPayoutTransitionError(DomainError):
    """Raised when a payout status update doesn't represent a valid transition."""
    pass
