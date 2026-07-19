# Low-Level Design (LLD)

## 1. Problem Recap

Affiliate sales enter the system as **Pending**. Users receive an **Advance
Payout of 10%** of a pending sale's earnings immediately. Later, an admin
reconciles each sale to **Approved** or **Rejected**, and the system
computes a **final payout** that accounts for the advance already paid.
Additionally, users are restricted to **one withdrawal every 24 hours**,
and any payout that later fails/is cancelled/is rejected must be
**credited back** to the user's balance so they can retry.

## 2. High-Level Workflow

```
                     ┌─────────────────────┐
                     │   Sale created       │
                     │   status = PENDING   │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Advance Payout Job    │
                     │ (idempotent, 10%)     │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  Admin Reconciliation │
                     │  -> APPROVED/REJECTED │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │ Final Payout Applied  │
                     │ to withdrawable_bal.  │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  User Withdraws       │
                     │  (24h cooldown rule)  │
                     └──────────┬───────────┘
                                │
                   ┌────────────▼─────────────┐
                   │ Payout later Fails/       │
                   │ Cancelled/Rejected?       │
                   │ -> credit back balance    │
                   └───────────────────────────┘
```

## 3. Core Entities

| Entity | Responsibility |
|---|---|
| `User` | Identity + running `withdrawable_balance` ledger + last withdrawal timestamp (for cooldown enforcement) |
| `Sale` | A single affiliate sale; tracks status, earning, and `advance_paid` (the idempotency anchor) |
| `Payout` | A generalized ledger entry for every money movement — advance, final adjustment, or withdrawal — with a lifecycle `status` |

See [`database-schema.md`](./database-schema.md) for full column-level detail
and [`class-design.md`](./class-design.md) for the corresponding Python
model/service structure.

## 4. Business Rule Enforcement — Design Rationale

### 4.1 Advance Payout Idempotency
**Rule:** "the same sale must never receive another advance payout, even
if the advance payout job runs multiple times."

**Design:** Rather than recomputing "has this sale been advanced" from a
transaction log each run (which requires a query + aggregation every
time), each `Sale` row carries its own `advance_paid` amount, defaulting
to `0`. The job's eligibility check is a single condition:
`status == PENDING AND advance_paid == 0`. This makes the check O(1) per
sale and trivially safe to re-run — a cron job triggering it hourly by
accident causes zero harm.

### 4.2 Final Payout Calculation
**Rule:** Approved → `earning - advance_paid`; Rejected → `-advance_paid`.

**Design:** Computed at the moment of reconciliation, inside the same
service call (and same DB transaction) that flips the sale's status. This
avoids a separate "calculate payouts" batch step that could run out of
sync with reconciliation — the two are atomic together. A `is_reconciled`
flag prevents the same sale from being reconciled (and its adjustment
applied) twice.

### 4.3 Withdrawal Cooldown
**Rule:** One withdrawal per 24 hours.

**Design:** `User.last_withdrawal_at` is checked against
`now - cooldown_hours` before allowing a new withdrawal. This avoids
needing a separate rate-limiter table or external service — the
constraint is naturally per-user and low-cardinality, so a single
timestamp column is sufficient and cheap to query.

### 4.4 Failed Payout Recovery (Question 2)
**Rule:** Failed/Cancelled/Rejected payouts must be credited back to the
withdrawable balance, and the user must be able to withdraw that amount
again.

**Design:** Every payout (advance, final, or withdrawal) is a row in the
single `Payout` ledger table with a lifecycle `status`. When a payout's
status transitions into a terminal bad state
(`failed`/`cancelled`/`rejected`), the service immediately credits the
payout's `amount` back onto `User.withdrawable_balance` and stamps
`recovered_at`. A defensive batch sweep endpoint additionally scans for
any bad-state payouts where `recovered_at IS NULL`, in case a processor
callback was missed — this makes recovery eventually-consistent even if
the real-time path fails.

## 5. Concurrency & Data Integrity Notes

- All balance-mutating operations (advance payout, reconciliation,
  withdrawal, recovery) run inside a single DB transaction per operation
  via SQLAlchemy's session — a partial failure (e.g. DB error mid-loop)
  will not leave the sale updated but the user's balance un-updated, or
  vice versa, for a *single* sale/payout.
- Batch reconciliation (`reconcile_sales_batch`) intentionally commits
  each sale's reconciliation independently rather than wrapping the whole
  batch in one transaction — see the trade-off discussion in
  [`design-decisions.md`](./design-decisions.md).
- Currency values are stored as `NUMERIC(12,2)` in Postgres and computed
  using Python's `Decimal` internally (converted to `float` only at the
  API boundary) to avoid floating-point rounding drift across repeated
  arithmetic.

## 6. Out of Scope (Explicitly)

To keep the implementation at an appropriate intern-level scope, the
following are intentionally **not** implemented, and would be natural
next steps in a production system:
- Authentication/authorization (admin vs. user roles) on endpoints
- Distributed locking for concurrent advance-payout job runs across
  multiple server instances (a single Postgres transaction is sufficient
  at this scale, but wouldn't scale to a multi-worker cron cluster
  without a `SELECT ... FOR UPDATE` or advisory lock)
- Real payment processor integration (all transfers are simulated as
  immediate `COMPLETED` status, with the status-update endpoint standing
  in for a webhook)
- Currency/locale support beyond a single implicit currency (₹, per the
  assignment)
