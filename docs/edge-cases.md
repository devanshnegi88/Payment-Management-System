# Edge Cases & Failure Scenarios

This document lists every edge case explicitly handled in the
implementation, why it matters, and where the handling lives in code.

---

## 1. Advance payout job runs more than once

**Scenario:** A cron job (or an impatient admin) triggers
`POST /payouts/advance/{user_id}` twice for the same user.

**Handling:** Each `Sale.advance_paid` starts at `0` and is only set once.
The job's query filters on `advance_paid == 0`, so already-advanced sales
are silently skipped (returned in `sales_skipped`, not re-paid).

**Where:** `advance_payout_service.run_advance_payout_for_user`
**Tested:** `test_advance_payout_is_idempotent_on_rerun`

---

## 2. Reconciling a sale that isn't Pending

**Scenario:** An admin tries to reconcile a sale that's already
`approved` or `rejected` (e.g. a duplicate button click, or stale data in
an admin UI).

**Handling:** `reconcile_sale` explicitly checks `sale.status == PENDING`
before proceeding, and raises `InvalidReconciliationError` (mapped to
HTTP `400`) otherwise.

**Where:** `reconciliation_service.reconcile_sale`
**Tested:** `test_cannot_reconcile_sale_that_is_not_pending`

---

## 3. Reconciling the same sale twice

**Scenario:** The reconciliation endpoint is called twice for the same
sale (e.g. a network retry after a slow response, or the admin re-submits
a form).

**Handling:** `is_reconciled` flag is checked defensively, and the
`status != PENDING` check (case 2 above) already blocks this in practice
once the first call succeeds and flips the status. Both checks exist so
the *intent* ("only once") is explicit in the code, not just an emergent
side effect of the status check.

**Tested:** `test_cannot_reconcile_same_sale_twice`

---

## 4. Batch reconciliation where one sale fails validation

**Scenario:** An admin submits `POST /sales/reconcile/batch` with 5 sale
IDs, but sale #3 was already reconciled by someone else moments earlier.

**Handling:** Each sale in the batch is reconciled independently, and
each call commits on success. If sale #3 raises `InvalidReconciliationError`,
sales #1 and #2 (already committed) are **not** rolled back — the error
propagates up and the caller sees which sale failed, but doesn't lose the
valid work already done.

**Trade-off:** This is deliberately *not* atomic across the whole batch.
The alternative (wrap the entire batch in one transaction, roll back
everything on any single failure) is arguably "more correct" in a strict
ACID sense, but would mean one stale row blocks an admin from processing
4 other perfectly valid reconciliations in the same request — worse for
the actual workflow this supports. See `design-decisions.md` for more.

---

## 5. Withdrawing with a zero balance

**Scenario:** A user calls `POST /withdrawals/{user_id}` but has never
received any payout, or already withdrew everything.

**Handling:** `withdraw()` checks `balance <= 0` and raises
`InsufficientBalanceError` (HTTP `400`) before creating any payout record.

**Tested:** `test_withdraw_raises_when_balance_is_zero`

---

## 6. Withdrawing before the 24-hour cooldown elapses

**Scenario:** A user withdraws, then immediately tries to withdraw again
(new earnings just landed).

**Handling:** `User.last_withdrawal_at` is compared against
`now - WITHDRAWAL_COOLDOWN_HOURS`. If the cooldown hasn't elapsed,
`WithdrawalCooldownError` is raised (HTTP `429`), with the exact
next-available timestamp included in the error message.

**Tested:** `test_withdraw_raises_cooldown_error_if_too_soon`,
`test_withdraw_allowed_after_cooldown_period_elapses`

---

## 7. Recovery vs. cooldown interaction

**Scenario:** A user withdraws ₹80, the payout fails at the bank an hour
later, the amount is credited back — can the user withdraw again right
away, or do they wait out the remainder of the original 24h cooldown?

**Handling:** In this implementation, recovery credits the balance but
**does not reset** `last_withdrawal_at`. The user must still wait until
24h have passed since their *original* withdrawal attempt, even though
that attempt ultimately failed.

**Why this design, not the alternative:** The assignment says recovery
should "allow the user to initiate another withdrawal for that amount" —
which is satisfied either way, since the money becomes withdrawable again
regardless of cooldown timing. Resetting the cooldown on every failure
would let a user (or a buggy processor bouncing payouts repeatedly)
withdraw far more often than the "once per 24h" rule intends, effectively
letting failures bypass the rate limit. Keeping the original cooldown
timer treats "withdraw" as the rate-limited action, not "successfully
receive money" — which better matches the plain reading of the business
rule. This is documented explicitly because it's a genuine judgment call,
not an oversight; a reasonable alternative design could argue the other
way, and this trade-off deserves conscious sign-off from a
product/business stakeholder in a real system.

---

## 8. The same payout status callback delivered twice

**Scenario:** A payment processor's webhook is retried (common with
at-least-once delivery guarantees), so `PATCH /payouts/{id}/status` with
`{"status": "failed"}` is received twice for the same payout.

**Handling:** `recovered_at` is set the first time recovery happens.
The second call sees `recovered_at IS NOT NULL` and skips crediting the
balance again.

**Tested:** `test_recovery_is_idempotent_does_not_double_credit`

---

## 9. A payout fails but the webhook is missed entirely

**Scenario:** The processor marks a payout `failed` in its own system,
but the webhook never reaches this service (network issue, service was
down, etc.) — so `payouts.status = 'failed'` in some external system, but
our DB doesn't reflect it (or does, via an out-of-band update, but
`recovered_at` was never set).

**Handling:** `POST /payouts/recover/{user_id}` is a defensive sweep that
queries for any payout with `status IN (failed, cancelled, rejected) AND
recovered_at IS NULL` and recovers it. Safe to call on a schedule (e.g.
hourly) as a reconciliation safety net.

**Tested:** `test_recovery_sweep_recovers_missed_failed_payouts`

---

## 10. Looking up a sale/user/payout that doesn't exist

**Scenario:** Any endpoint referencing an ID that isn't in the DB.

**Handling:** Every service function checks for `None` after the query
and raises the appropriate `*NotFoundError`, mapped to HTTP `404` at the
route layer. A global `DomainError` handler in `main.py` is a fallback
in case any route forgets to catch a specific exception type explicitly.

---

## 11. Currency rounding errors compounding across many calculations

**Scenario:** Repeated float arithmetic (e.g. summing many small advance
payouts) can silently drift due to binary floating-point representation
error.

**Handling:** All monetary values are stored as `NUMERIC(12,2)` in
Postgres and computed using Python's `Decimal` type inside every service
function — floats are only used at the very edge, when serializing to a
Pydantic response schema.

---

## 12. A sale is rejected without ever having received an advance

**Scenario:** A sale sits pending but the advance payout job never ran
for it (e.g. it was created and reconciled within the same minute, before
any scheduled job fired) — then it's reconciled as `rejected`.

**Handling:** `advance_paid` remains `0`, so the adjustment calculation
`-advance_paid` correctly evaluates to `0` — no incorrect clawback is
ever applied against money the user never actually received.

---

## 13. Negative or zero earnings on sale creation

**Scenario:** A malformed request tries to create a sale with `earning: 0`
or `earning: -10`.

**Handling:** `SaleCreate.earning` uses Pydantic's `Field(..., gt=0)`,
so the request is rejected with a `422 Unprocessable Entity` before it
ever reaches the database or service layer.
