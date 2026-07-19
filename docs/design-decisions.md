# Design Decisions & Trade-offs

This consolidates every major design decision made across the project,
with the alternative considered and why the chosen approach won out.
Individual decisions are also noted inline in code comments and in
`LLD.md`/`edge-cases.md`; this document is the single place to see all of
them together.

---

### 1. One `Payout` table for advance, final, and withdrawal entries

**Chosen:** A single table with a `payout_type` enum column.
**Alternative:** Three separate tables (`AdvancePayout`, `FinalPayout`,
`Withdrawal`).
**Why:** Question 2's recovery logic needs to scan for
failed/cancelled/rejected payouts *regardless of type* — one table means
one query. A full payout history/audit trail for a user is also a single
join instead of a `UNION` across three tables.
**Trade-off accepted:** `sale_id` is nullable (withdrawals aren't
per-sale), a minor schema smell. Judged acceptable given how much it
simplifies recovery and history queries.

---

### 2. Stateless service functions instead of service classes

**Chosen:** `def run_advance_payout_for_user(db: Session, user_id: str)`
style functions.
**Alternative:** `AdvancePayoutService(db).run_for_user(user_id)` classes
with `__init__(self, db)`.
**Why:** No per-instance state exists beyond the DB session, which
FastAPI already provides per-request via `Depends(get_db)`. Functions are
trivially testable without instantiating or mocking anything.
**Trade-off accepted:** Slightly less "enterprise-Java-familiar" for
reviewers expecting OOP service layers — addressed explicitly in
`class-design.md` §5 so it reads as a deliberate choice, not an omission.

---

### 3. Batch reconciliation commits per-sale, not per-batch

**Chosen:** Each sale in `reconcile_sales_batch` is reconciled and
committed independently.
**Alternative:** Wrap the entire batch in one transaction; roll back
everything if any single sale fails.
**Why:** One stale/already-reconciled sale in a 50-sale admin batch
shouldn't block the other 49 valid reconciliations.
**Trade-off accepted:** The batch is not atomic — a caller must handle a
partial-success response. Documented explicitly in `edge-cases.md` §4.

---

### 4. Withdrawal cooldown timer isn't reset by recovery

**Chosen:** `last_withdrawal_at` is only set when a withdrawal is
initiated, never touched by the recovery flow.
**Alternative:** Reset the cooldown when a failed withdrawal is
recovered, letting the user retry immediately.
**Why:** Treats "attempting a withdrawal" as the rate-limited action.
Resetting on every failure would let repeated processor failures
(malicious or accidental) bypass the "one withdrawal per 24h" rule
entirely.
**Trade-off accepted:** A user whose withdrawal fails through no fault of
their own still waits out the original cooldown. Flagged explicitly as a
judgment call in `edge-cases.md` §7 that a real product owner should
weigh in on.

---

### 5. Auto-creating a `User` on first `Sale` creation

**Chosen:** `POST /sales` creates the referenced user if `user_id` isn't
found yet, rather than requiring a separate `POST /users` call first.
**Alternative:** Require explicit user creation before any sale can
reference them (stricter referential integrity at the API level).
**Why:** The assignment's reference data shows sales carrying a raw
`userId` string with no separate onboarding step — matching that shape
keeps the API surface minimal and matches how the reference JSON is
structured.
**Trade-off accepted:** A typo'd `user_id` silently creates a new "ghost"
user instead of erroring — acceptable for this scope, but a production
system would likely want an explicit user registration flow with
validation.

---

### 6. Payouts default to `COMPLETED` immediately (no `PENDING` transfer state)

**Chosen:** Advance, final, and withdrawal payouts are all recorded as
`COMPLETED` at creation time; a payout only becomes `FAILED`/`CANCELLED`/
`REJECTED` via an explicit follow-up call to
`PATCH /payouts/{id}/status`, simulating a processor callback.
**Alternative:** Model payouts as starting `PENDING` and requiring a
separate "confirm" step before they're considered real.
**Why:** Keeps the "happy path" (advance → reconcile → withdraw) simple
to exercise and test, while Question 2's entire premise — that a payout
succeeds first, then later fails — is naturally represented as a status
*transition* rather than requiring a whole separate pending-confirmation
workflow.
**Trade-off accepted:** Doesn't model a payment gateway's real async
initiation-then-confirmation flow — acceptable since the assignment's
Question 2 explicitly only cares about the *failure* side of that flow.

---

### 7. Alembic as the single source of schema truth (no `create_all()` fallback)

**Chosen:** Tables are only ever created via `alembic upgrade head`.
**Alternative:** Also call `Base.metadata.create_all(engine)` on app
startup as a dev convenience.
**Why:** Having two different code paths that can create the schema
(migrations vs. auto-create) risks them silently drifting apart — a
classic source of "works on my machine" bugs. The assignment's tech
stack explicitly lists Alembic, so it should be the only mechanism.
**Trade-off accepted:** Slightly more setup friction for a first-time
runner (must remember to run migrations) — mitigated by clear README
setup instructions.

---

### 8. In-memory SQLite for tests instead of a live PostgreSQL instance

**Chosen:** `tests/conftest.py` spins up a fresh `sqlite:///:memory:`
database per test.
**Alternative:** Require a running Postgres instance (e.g. via
`docker-compose` + a test database) for `pytest` to work at all.
**Why:** Every type used in the models (`Enum`, `Numeric`, `DateTime`,
`ForeignKey`) is supported identically by SQLAlchemy across both
dialects, so behavior under test is equivalent. Zero-setup tests are far
more likely to actually get run — by a grader, a CI pipeline, or the
next contributor.
**Trade-off accepted:** SQLite doesn't enforce Postgres-specific behavior
(e.g. certain constraint timing, native enum type quirks) — acceptable
since none of that is exercised by this project's business logic.

---

### 9. Decimal-based currency arithmetic throughout the service layer

**Chosen:** All service functions convert `Numeric` DB values to Python
`Decimal` for every calculation, converting to `float` only at the
Pydantic schema boundary.
**Alternative:** Use `float` throughout, since Pydantic/JSON only
understand floats anyway.
**Why:** Repeated float arithmetic across many advance/final payout
calculations can silently accumulate rounding error. `Decimal` avoids
this entirely within the service layer, where it matters.
**Trade-off accepted:** Slightly more verbose code (`Decimal(str(x))`
conversions) — judged worth it for correctness on financial calculations.

---

### 10. No authentication/authorization layer

**Chosen:** All endpoints (including admin reconciliation) are open, with
no auth middleware.
**Alternative:** Add API-key or JWT-based auth distinguishing admin vs.
regular user endpoints.
**Why:** Explicitly out of scope per the assignment's focus on payout LLD
specifically, and adding a full auth system would dilute the submission's
focus on the actual business logic being evaluated.
**Trade-off accepted:** Documented explicitly as a known gap in
`LLD.md` §6 ("Out of Scope") — not a hidden omission, and a natural next
step called out for a production version of this system.
