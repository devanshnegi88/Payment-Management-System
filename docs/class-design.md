# Class Design

Python doesn't force an OOP style for business logic the way Java might,
so this project uses a hybrid: **ORM entities are classes** (SQLAlchemy
models), while **business logic lives in stateless service functions**
rather than service *classes*. This section documents both, plus how they
map to the assignment's required "class design."

## 1. ORM Model Classes (`app/models/`)

### `User(Base)`
```
+-------------------------------+
| User                          |
+-------------------------------+
| id: int (PK)                  |
| user_id: str (unique)         |
| name: str                     |
| withdrawable_balance: Decimal |
| last_withdrawal_at: datetime? |
| created_at: datetime          |
+-------------------------------+
| sales: list[Sale]             |
| payouts: list[Payout]         |
+-------------------------------+
```

### `Sale(Base)`
```
+-------------------------------+
| Sale                          |
+-------------------------------+
| id: int (PK)                  |
| user_id: int (FK -> User)     |
| brand: str                    |
| status: SaleStatus            |
| earning: Decimal              |
| advance_paid: Decimal         |
| is_reconciled: bool           |
| created_at: datetime          |
| reconciled_at: datetime?      |
+-------------------------------+
| user: User                    |
+-------------------------------+
```

### `Payout(Base)`
```
+-------------------------------+
| Payout                        |
+-------------------------------+
| id: int (PK)                  |
| user_id: int (FK -> User)     |
| sale_id: int? (FK -> Sale)    |
| payout_type: PayoutType       |
| status: PayoutStatus          |
| amount: Decimal               |
| created_at: datetime          |
| recovered_at: datetime?       |
+-------------------------------+
| user: User                    |
| sale: Sale?                   |
+-------------------------------+
```

### Enums
- `SaleStatus`: `PENDING`, `APPROVED`, `REJECTED`
- `PayoutType`: `ADVANCE`, `FINAL`, `WITHDRAWAL`
- `PayoutStatus`: `PENDING`, `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`

## 2. Service Layer (`app/services/`)

Each service module is a **stateless collection of functions** taking a
`Session` as an explicit parameter, rather than a class with injected
dependencies. This is a deliberate simplicity choice — see
[`design-decisions.md`](./design-decisions.md).

| Module | Function | Responsibility |
|---|---|---|
| `advance_payout_service.py` | `run_advance_payout_for_user(db, user_id)` | Pays 10% advance on all eligible pending sales for one user; idempotent |
| | `run_advance_payout_for_all_users(db)` | Batch wrapper across all users |
| `reconciliation_service.py` | `reconcile_sale(db, sale_id, status)` | Reconciles one sale, computes and applies the final payout adjustment |
| | `reconcile_sales_batch(db, user_id, reconciliations)` | Reconciles multiple sales, returns an aggregated summary |
| `withdrawal_service.py` | `withdraw(db, user_id)` | Withdraws the user's full balance, enforcing the 24h cooldown |
| `recovery_service.py` | `update_payout_status(db, payout_id, status)` | Simulates a processor callback; auto-recovers on bad terminal status |
| | `recover_unrecovered_failed_payouts(db, user_id)` | Defensive batch sweep for missed recoveries |

## 3. Schema Classes (`app/schemas/`)

Pydantic `BaseModel` subclasses define the request/response contracts,
kept deliberately separate from the ORM classes above so:
1. Internal-only fields (like `is_reconciled`) are never accidentally
   leaked unless explicitly included in a response schema.
2. External IDs (`user_id` as a string) can differ in shape from internal
   foreign keys (`user_id` as an int) without any ambiguity.

Key schema classes: `SaleCreate`, `SaleResponse`, `SaleReconcileRequest`,
`PayoutResponse`, `AdvancePayoutResult`, `FinalPayoutResult`, `UserCreate`,
`UserResponse`, `WithdrawalRequest`, `WithdrawalResponse`.

## 4. Exception Hierarchy (`app/utils/exceptions.py`)

```
DomainError (base)
├── UserNotFoundError
├── SaleNotFoundError
├── PayoutNotFoundError
├── InvalidReconciliationError
├── WithdrawalCooldownError
├── InsufficientBalanceError
└── InvalidPayoutTransitionError
```

All inherit from a common `DomainError` base so `main.py` can register a
single catch-all FastAPI exception handler as a defensive fallback, while
individual routes still catch specific subclasses for precise HTTP status
codes (404 vs 400 vs 429).

## 5. Why Not "Service Classes"?

A more Java-influenced design might use `AdvancePayoutService`,
`ReconciliationService` classes with `__init__(self, db: Session)` and
instance methods. This project intentionally avoids that pattern because:
- There's no per-instance state to hold — every function's only dependency
  is the `db` session, passed explicitly, which is more idiomatic in
  Python/FastAPI (matches how `Depends(get_db)` already works).
- It keeps functions trivially unit-testable — call them directly with a
  test session, no class instantiation/mocking required (see `tests/`).
- Wrapping stateless functions in a class adds a layer of indirection
  without adding any actual encapsulation benefit here.
