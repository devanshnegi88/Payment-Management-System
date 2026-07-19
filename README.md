# Payout Management System

A backend system for managing **advance payouts** and **final reconciliation payouts**
for affiliate sales, built with FastAPI, SQLAlchemy, and PostgreSQL.

---

## 1. Problem Overview

Every affiliate sale starts as **Pending**. Users get an **advance payout of 10%**
of pending earnings immediately. Later, an admin reconciles each sale to
**Approved** or **Rejected**, and the system computes the user's **final payout**,
accounting for whatever advance was already paid.

Key business rules implemented:

1. **Advance Payout** — 10% of a Pending sale's earnings, paid at most once per sale
   (idempotent even if the job re-runs).
2. **Final Payout on Reconciliation**
   - Approved → `earning - advance_paid`
   - Rejected → `-advance_paid` (clawback, since the user wasn't entitled to it)
3. **Withdrawal Restriction** — one withdrawal per user every 24 hours.
4. **Failed Payout Recovery** — if a payout is Cancelled/Rejected/Failed, the amount
   is credited back to the user's withdrawable balance so they can retry.

---

## 2. Architecture

This project uses a **layered architecture**: `Routes → Services → Models`.

- **`routes/`** — FastAPI routers. Handle HTTP request/response only, no business logic.
- **`services/`** — All business logic (advance payout calculation, reconciliation,
  withdrawal cooldown enforcement, payout recovery). This is the core of the LLD.
- **`models/`** — SQLAlchemy ORM entities representing the database schema.
- **`schemas/`** — Pydantic models for request validation and response serialization,
  kept separate from ORM models so internal fields are never accidentally exposed.

### Why not a more complex architecture?

Patterns like Clean Architecture / Hexagonal (with repository interfaces, use-case
classes, dependency inversion containers) are common in production-grade systems,
but for a project of this scope they add ceremony without real benefit. A layered
service-based architecture is the appropriate level of complexity for an SDE Intern
assignment — it still demonstrates separation of concerns, but stays readable.

`core/` was merged into `config.py` (settings) and `utils/exceptions.py` (custom
errors), since there isn't enough cross-cutting infrastructure (auth, middleware,
logging config, etc.) in this project to justify a dedicated package.

**Full write-up:** [`docs/LLD.md`](./docs/LLD.md)

---

## 3. Project Structure

```
payout-management-system/
├── app/
│   ├── main.py                  # FastAPI app entrypoint + global exception handling
│   ├── database.py              # DB engine, session, Base
│   ├── config.py                # Settings via Pydantic BaseSettings
│   ├── models/                  # SQLAlchemy ORM entities (User, Sale, Payout)
│   ├── schemas/                 # Pydantic request/response contracts
│   ├── services/                # Business logic (advance, reconciliation, withdrawal, recovery)
│   ├── routes/                  # FastAPI routers (sales, payouts, withdrawals)
│   └── utils/exceptions.py      # Custom domain exception hierarchy
├── alembic/                     # Database migrations
├── tests/                       # pytest suite (in-memory SQLite, no DB setup needed)
├── docs/                        # Full deliverable documentation (see below)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. Database Schema

- **User** — tracks identity + `withdrawable_balance`.
- **Sale** — a single affiliate sale; tracks `status`, `earning`, and whether an
  advance has been paid (`advance_paid` amount — the idempotency anchor).
- **Payout** — a record of any payout event (advance, final, or a withdrawal),
  including its lifecycle status (`pending`, `completed`, `failed`, `cancelled`,
  `rejected`), so history is auditable and recovery is possible.

**Full schema, ER diagram, indexes, and relationships:**
[`docs/database-schema.md`](./docs/database-schema.md)

---

## 5. Setup Instructions

### Prerequisites
- Python 3.11+
- PostgreSQL running locally (or accessible via `DATABASE_URL`)

### Steps

```bash
# 1. Clone the repo
git clone <repo-url>
cd payout-management-system

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# edit .env with your actual PostgreSQL credentials

# 5. Run database migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`.

No Postgres locally? The fastest option is Docker:
```bash
docker run --name payout-db \
  -e POSTGRES_USER=payout_user -e POSTGRES_PASSWORD=payout_password \
  -e POSTGRES_DB=payout_management -p 5432:5432 -d postgres
```
The default `.env.example` values already match this command.

---

## 6. API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sales` | Create a sale (auto-creates the user if new) |
| `GET` | `/sales/{sale_id}` | Fetch one sale |
| `GET` | `/sales?user_id=...` | List a user's sales |
| `PATCH` | `/sales/{sale_id}/reconcile` | Reconcile one sale to approved/rejected |
| `POST` | `/sales/reconcile/batch` | Reconcile several sales, get aggregated final payout |
| `POST` | `/payouts/advance/{user_id}` | Run the advance payout job for one user |
| `POST` | `/payouts/advance` | Run the advance payout job for all users |
| `GET` | `/payouts?user_id=...` | Full payout ledger for a user |
| `PATCH` | `/payouts/{payout_id}/status` | Simulate a processor callback (triggers recovery) |
| `POST` | `/payouts/recover/{user_id}` | Manual recovery sweep for missed callbacks |
| `POST` | `/withdrawals/{user_id}` | Withdraw full balance (24h cooldown enforced) |
| `GET` | `/health` | Liveness check |

**Full docs with request/response examples and an end-to-end curl walkthrough:**
[`docs/api-documentation.md`](./docs/api-documentation.md)

---

## 7. Class Design

ORM entity classes, the stateless service-function layer, schema classes, and the
custom exception hierarchy — including why service *classes* were deliberately not
used. See [`docs/class-design.md`](./docs/class-design.md).

---

## 8. Edge Cases & Failure Scenarios

13 explicitly handled scenarios, each with the reasoning, code location, and test
coverage — including advance-payout idempotency, double reconciliation, withdrawal
cooldown vs. recovery interaction, missed webhook recovery sweeps, and currency
rounding safety. See [`docs/edge-cases.md`](./docs/edge-cases.md).

---

## 9. Running Tests

Tests run against an **in-memory SQLite database** — no Postgres setup required to
run the suite.

```bash
pytest tests/ -v
```

Coverage:
- `test_advance_payout.py` — 10% calculation, the assignment's ₹120→₹12 example, idempotency on re-run
- `test_reconciliation.py` — Approved/Rejected final payout math, the full ₹68 worked example, reconciliation idempotency
- `test_withdrawal.py` — 24-hour cooldown enforcement, insufficient balance, successful withdrawal
- `test_recovery.py` — Failed/cancelled/rejected credit-back (Question 2), and recovery idempotency

---

## 10. Design Decisions & Trade-offs

Every major design choice made in this project — the single `Payout` ledger table,
stateless services over service classes, non-atomic batch reconciliation, the
cooldown/recovery interaction, Decimal-based currency math, and more — each with the
alternative considered and why it wasn't chosen.

**Full write-up:** [`docs/design-decisions.md`](./docs/design-decisions.md)

---

## Documentation Index

| Doc | Covers |
|---|---|
| [`docs/LLD.md`](./docs/LLD.md) | Overall workflow, entity responsibilities, business rule rationale |
| [`docs/database-schema.md`](./docs/database-schema.md) | ER diagram, column-level schema, indexes, relationships |
| [`docs/class-design.md`](./docs/class-design.md) | Model classes, service layer, schemas, exception hierarchy |
| [`docs/api-documentation.md`](./docs/api-documentation.md) | Every endpoint with request/response examples |
| [`docs/edge-cases.md`](./docs/edge-cases.md) | 13 handled edge cases with reasoning and test references |
| [`docs/design-decisions.md`](./docs/design-decisions.md) | All trade-offs consolidated in one place |
