# 💰 Payout Management System

> **A backend payout and reconciliation system for affiliate sales, supporting advance payouts, final settlement, withdrawal controls, idempotent processing, and failed-payout recovery.**

<div align="center">

**FastAPI • PostgreSQL • SQLAlchemy • Alembic • Pydantic • Pytest**

</div>

---

## 🛠️ Tech Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-Migrations-499848?style=flat-square)
![Pydantic](https://img.shields.io/badge/Pydantic-Validation-E92063?style=flat-square)
![Pytest](https://img.shields.io/badge/Pytest-Testing-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Test%20DB-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerization-2496ED?style=flat-square&logo=docker&logoColor=white)

</div>

---

# 📌 Overview

The **Payout Management System** is a backend service designed to manage the complete payout lifecycle for affiliate sales.

Every affiliate sale begins in a **Pending** state. The system can issue an **advance payout of 10%** of the sale's earnings. Later, an administrator reconciles the sale as either **Approved** or **Rejected**, after which the system calculates the final payout while accounting for any advance that has already been paid.

The system also handles:

- 💸 Advance payouts
- 🧾 Final reconciliation payouts
- 🔁 Idempotent payout processing
- ⏱️ 24-hour withdrawal cooldowns
- ♻️ Failed payout recovery
- 💰 Withdrawable balance management
- 📒 Auditable payout ledger
- 🧮 Decimal-based currency calculations
- 🧪 Comprehensive business-rule testing

---

# 💼 Problem Overview

The core business flow is:

```text
                 Affiliate Sale
                       │
                       ▼
                  ┌─────────┐
                  │ Pending │
                  └────┬────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
   Advance Payout             Reconciliation
       10%                         │
                                   ▼
                         ┌─────────┴─────────┐
                         │                   │
                         ▼                   ▼
                      Approved           Rejected
                         │                   │
                         ▼                   ▼
                  Final Settlement       Clawback
```

---

# 💰 Core Business Rules

## 1. Advance Payout

A Pending sale is eligible for an advance payout equal to:

```text
Advance = 10% × Sale Earnings
```

The advance can be paid **at most once per sale**.

The `advance_paid` amount acts as the idempotency anchor, making the operation safe even if the payout job is executed multiple times.

### Example

```text
Sale Earnings = ₹120

Advance = 10% × ₹120
        = ₹12
```

---

## 2. Final Payout on Reconciliation

When an administrator reconciles a sale, the final payout depends on the outcome.

### Approved

```text
Final Payout = Earning − Advance Paid
```

### Rejected

```text
Final Payout = −Advance Paid
```

The negative amount represents a **clawback**, because the user was not ultimately entitled to the advance.

---

## 3. Withdrawal Restriction

Each user can make only:

```text
1 withdrawal every 24 hours
```

The cooldown is enforced by the service layer.

---

## 4. Failed Payout Recovery

If a payout becomes:

```text
Cancelled
Rejected
Failed
```

the amount is credited back to the user's **withdrawable balance**.

This allows the user to retry the payout instead of permanently losing the amount.

---

# 🏗️ Architecture

The project follows a simple **layered architecture**:

```text
┌────────────────────────────────┐
│          FastAPI Routes        │
│        HTTP Request/Response   │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│         Service Layer          │
│                                │
│  • Advance Payout              │
│  • Reconciliation              │
│  • Withdrawal                  │
│  • Recovery                    │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│       SQLAlchemy Models        │
│         ORM Entities           │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│          PostgreSQL            │
└────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| `routes/` | FastAPI routers and HTTP handling |
| `services/` | Business rules and domain workflows |
| `models/` | SQLAlchemy ORM entities |
| `schemas/` | Pydantic request/response contracts |
| `utils/` | Custom domain exceptions |
| `database.py` | Database engine, sessions, and Base |
| `config.py` | Application configuration |

---

# 🧠 Why Layered Architecture?

The project intentionally avoids unnecessary architectural complexity.

Patterns such as:

- Clean Architecture
- Hexagonal Architecture
- Repository interfaces
- Dedicated use-case classes
- Dependency-injection containers

can be useful in larger production systems, but for this project's scope they would introduce additional ceremony without providing significant benefit.

The layered service-based architecture provides:

- Clear separation of concerns
- Easy navigation
- Testable business logic
- Minimal abstraction
- Straightforward dependency flow

```text
Routes
   ↓
Services
   ↓
Models
   ↓
Database
```

The `core/` package was also intentionally merged into:

```text
config.py
utils/exceptions.py
```

because the project does not currently contain enough cross-cutting infrastructure to justify a separate package.

---

# 🔄 End-to-End Payout Lifecycle

```text
                     Create Sale
                          │
                          ▼
                    ┌──────────┐
                    │ Pending  │
                    └────┬─────┘
                         │
                         ▼
                Advance Payout Job
                         │
                         ▼
                  Calculate 10%
                         │
                         ▼
                  Create Payout
                         │
                         ▼
                Update User Balance
                         │
                         ▼
                  Mark Advance Paid
                         │
                         ▼
                 Admin Reconciliation
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
          Approved               Rejected
              │                     │
              ▼                     ▼
       Earning - Advance       -Advance Paid
              │                     │
              └──────────┬──────────┘
                         ▼
                   Final Payout
                         │
                         ▼
                  Payout Ledger
                         │
                         ▼
                Withdrawal / Recovery
```

---

# 🗄️ Database Design

The system uses three primary business entities.

## 👤 User

Tracks:

- User identity
- `withdrawable_balance`

---

## 🛒 Sale

Represents a single affiliate sale.

Important fields include:

- `status`
- `earning`
- `advance_paid`
- User relationship

The `advance_paid` value is also used as the idempotency anchor for advance processing.

---

## 💸 Payout

Represents a financial payout event.

A payout can represent:

- Advance payout
- Final payout
- Withdrawal

Supported lifecycle states:

```text
pending
completed
failed
cancelled
rejected
```

Keeping payout events in a ledger provides an auditable history and enables recovery processing.

---

# 📊 Data Model

```text
┌──────────────────────┐
│         User         │
├──────────────────────┤
│ id                   │
│ withdrawable_balance │
└──────────┬───────────┘
           │
           │ 1:N
           ▼
┌──────────────────────┐
│        Sale          │
├──────────────────────┤
│ id                   │
│ user_id              │
│ status               │
│ earning              │
│ advance_paid         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│       Payout         │
├──────────────────────┤
│ id                   │
│ user_id              │
│ sale_id              │
│ type                 │
│ amount               │
│ status               │
└──────────────────────┘
```

Detailed ER diagrams, relationships, indexes, and schema definitions are documented in:

`docs/database-schema.md`

---

# 📁 Project Structure

```text
payout-management-system/
│
├── app/
│   ├── main.py                  # FastAPI entrypoint + exception handling
│   ├── database.py              # DB engine, session, Base
│   ├── config.py                # Application settings
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── sale.py
│   │   └── payout.py
│   │
│   ├── schemas/
│   │   └── ...                  # Pydantic contracts
│   │
│   ├── services/
│   │   ├── advance.py
│   │   ├── reconciliation.py
│   │   ├── withdrawal.py
│   │   └── recovery.py
│   │
│   ├── routes/
│   │   ├── sales.py
│   │   ├── payouts.py
│   │   └── withdrawals.py
│   │
│   └── utils/
│       └── exceptions.py        # Domain exception hierarchy
│
├── alembic/                     # Database migrations
│
├── tests/
│   ├── test_advance_payout.py
│   ├── test_reconciliation.py
│   ├── test_withdrawal.py
│   └── test_recovery.py
│
├── docs/
│   ├── LLD.md
│   ├── database-schema.md
│   ├── class-design.md
│   ├── api-documentation.md
│   ├── edge-cases.md
│   └── design-decisions.md
│
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🔌 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/sales` | Create a sale and auto-create user if new |
| `GET` | `/sales/{sale_id}` | Fetch a single sale |
| `GET` | `/sales?user_id=...` | List user's sales |
| `PATCH` | `/sales/{sale_id}/reconcile` | Reconcile a sale |
| `POST` | `/sales/reconcile/batch` | Batch reconcile sales |
| `POST` | `/payouts/advance/{user_id}` | Run advance payout for one user |
| `POST` | `/payouts/advance` | Run advance payout for all users |
| `GET` | `/payouts?user_id=...` | Fetch user's payout ledger |
| `PATCH` | `/payouts/{payout_id}/status` | Simulate processor callback |
| `POST` | `/payouts/recover/{user_id}` | Run manual recovery sweep |
| `POST` | `/withdrawals/{user_id}` | Withdraw full available balance |
| `GET` | `/health` | Liveness check |

Detailed request/response examples are available in:

`docs/api-documentation.md`

---

# 💸 Advance Payout Processing

The advance payout job follows this flow:

```text
Pending Sales
      │
      ▼
Find unpaid advances
      │
      ▼
Calculate 10%
      │
      ▼
Create Payout
      │
      ▼
Credit User Balance
      │
      ▼
Mark advance_paid
```

### Idempotency

The job can safely run more than once.

```text
First Run
   │
   ├── Calculate advance
   ├── Create payout
   └── Mark advance_paid
          │
          ▼
Second Run
   │
   └── Already paid → Skip
```

This prevents duplicate advance payouts when a scheduled job is retried.

---

# 🧾 Reconciliation

The reconciliation flow supports two outcomes:

```text
                    Pending
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
          Approved           Rejected
              │                 │
              ▼                 ▼
      Earning - Advance     -Advance Paid
              │                 │
              └────────┬────────┘
                       ▼
                 Final Payout
```

Reconciliation is designed to be idempotent so that the same sale cannot be financially settled multiple times.

---

# 🔁 Batch Reconciliation

The API supports reconciling multiple sales in one request:

```http
POST /sales/reconcile/batch
```

The batch workflow processes the selected sales and returns an aggregated final payout result.

The project deliberately documents the trade-off around **non-atomic batch reconciliation** rather than treating the entire batch as one all-or-nothing transaction.

See:

`docs/design-decisions.md`

---

# ♻️ Payout Recovery

Processor callbacks can move payouts into failure states.

```text
                    Payout
                      │
                      ▼
              Processor Callback
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
   completed        failed       cancelled
       │              │              │
       ▼              └──────┬───────┘
     No Action               │
                             ▼
                     Credit Balance
```

Rejected payouts are also eligible for recovery.

### Manual Recovery

If a processor callback is missed, a manual recovery sweep can be triggered:

```http
POST /payouts/recover/{user_id}
```

Recovery is designed to be idempotent.

---

# ⏱️ Withdrawal Cooldown

The system enforces one withdrawal per user every 24 hours.

```text
Withdrawal Request
        │
        ▼
Check Last Withdrawal
        │
        ▼
   Within 24 Hours?
      │         │
     Yes        No
      │          │
      ▼          ▼
    Reject      Allow
                  │
                  ▼
           Withdraw Balance
```

The implementation also considers the interaction between:

```text
Withdrawal Cooldown
        +
Payout Recovery
```

so that recovery does not unintentionally bypass the withdrawal restriction.

---

# 🧮 Financial Precision

All currency calculations use **Decimal-based arithmetic** rather than floating-point arithmetic.

This is important for:

- Advance calculations
- Final settlement
- Clawbacks
- Balance updates
- Withdrawals
- Currency rounding

### Example

```text
Sale Earnings = ₹120

Advance = ₹120 × 10%
        = ₹12
```

The test suite includes the assignment's ₹120 → ₹12 example as well as the complete ₹68 reconciliation example.

---

# 🛡️ Error Handling

The application uses a custom domain exception hierarchy located in:

```text
app/utils/exceptions.py
```

This keeps business-specific failures separate from generic framework errors and allows the FastAPI layer to translate domain errors into appropriate HTTP responses.

---

# 🧪 Testing

The test suite runs against an **in-memory SQLite database**.

This means PostgreSQL does not need to be configured locally just to execute the tests.

Run:

```bash
pytest tests/ -v
```

---

## ✅ Test Coverage

### `test_advance_payout.py`

Covers:

- 10% advance calculation
- ₹120 → ₹12 example
- Advance payout creation
- Idempotent job reruns

### `test_reconciliation.py`

Covers:

- Approved final payout
- Rejected final payout
- Advance deduction
- ₹68 worked example
- Reconciliation idempotency

### `test_withdrawal.py`

Covers:

- 24-hour cooldown
- Insufficient balance
- Successful withdrawal

### `test_recovery.py`

Covers:

- Failed payout recovery
- Cancelled payout recovery
- Rejected payout recovery
- Balance credit-back
- Recovery idempotency

---

# ⚠️ Edge Cases & Failure Scenarios

The implementation explicitly handles **13 edge cases**.

Important scenarios include:

- Duplicate advance payout execution
- Double reconciliation
- Withdrawal cooldown
- Insufficient balance
- Failed payout recovery
- Cancelled payout recovery
- Rejected payout recovery
- Missed processor callbacks
- Recovery sweeps
- Recovery/cooldown interaction
- Currency rounding safety
- Idempotent recovery
- Idempotent reconciliation

Detailed reasoning and test references:

`docs/edge-cases.md`

---

# ⚙️ Setup

## Prerequisites

- Python **3.11+**
- PostgreSQL
- `pip`
- Virtual environment

---

## 1. Clone the Repository

```bash
git clone <repo-url>
cd payout-management-system
```

---

## 2. Create Virtual Environment

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment

```bash
cp .env.example .env
```

Update `.env` with your PostgreSQL credentials.

---

## 5. Run Database Migrations

```bash
alembic upgrade head
```

---

## 6. Start the Server

```bash
uvicorn app.main:app --reload
```

Application:

```text
http://127.0.0.1:8000
```

Interactive Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 🐘 PostgreSQL with Docker

If PostgreSQL is not installed locally, run:

```bash
docker run --name payout-db \
  -e POSTGRES_USER=payout_user \
  -e POSTGRES_PASSWORD=payout_password \
  -e POSTGRES_DB=payout_management \
  -p 5432:5432 \
  -d postgres
```

The default `.env.example` values are designed to match this configuration.

---

# 🐳 Docker

The application can be containerized together with its PostgreSQL dependency.

Example PostgreSQL container:

```bash
docker run --name payout-db \
  -e POSTGRES_USER=payout_user \
  -e POSTGRES_PASSWORD=payout_password \
  -e POSTGRES_DB=payout_management \
  -p 5432:5432 \
  -d postgres
```

---

# 📚 Documentation

The project includes dedicated engineering documentation.

| Document | Description |
|---|---|
| [`docs/LLD.md`](./docs/LLD.md) | Overall workflow, entity responsibilities, and business-rule rationale |
| [`docs/database-schema.md`](./docs/database-schema.md) | ER diagram, schema, indexes, and relationships |
| [`docs/class-design.md`](./docs/class-design.md) | Model classes, service layer, schemas, and exceptions |
| [`docs/api-documentation.md`](./docs/api-documentation.md) | API endpoints with request/response examples |
| [`docs/edge-cases.md`](./docs/edge-cases.md) | 13 handled edge cases and test references |
| [`docs/design-decisions.md`](./docs/design-decisions.md) | Architecture and implementation trade-offs |

---

# 🧠 Design Decisions & Trade-offs

The project documents the reasoning behind its major engineering decisions.

### Single Payout Ledger

A single `Payout` table records:

- Advance payouts
- Final payouts
- Withdrawals

This provides a centralized financial history.

### Stateless Services

Business logic is implemented through service functions rather than stateful service classes.

### Decimal Currency Math

`Decimal` is used for financial calculations to avoid floating-point precision problems.

### Idempotent Operations

Advance payouts, reconciliation, and recovery can safely handle repeated execution.

### Non-Atomic Batch Reconciliation

Batch reconciliation is intentionally not implemented as one all-or-nothing transaction, allowing individual sale processing to proceed independently.

### Simple Architecture

The project avoids abstractions that do not provide meaningful value at its current scope.

---

# 📈 Engineering Highlights

```text
┌─────────────────────────────────────────────┐
│              PAYOUT ENGINE                  │
├─────────────────────────────────────────────┤
│                                             │
│  Affiliate Sale                             │
│       ↓                                     │
│  10% Advance Payout                         │
│       ↓                                     │
│  Idempotent Processing                      │
│       ↓                                     │
│  Admin Reconciliation                       │
│       ↓                                     │
│  Approved / Rejected Settlement             │
│       ↓                                     │
│  Auditable Payout Ledger                    │
│       ↓                                     │
│  Processor Status                           │
│       ↓                                     │
│  Failed Payout Recovery                     │
│       ↓                                     │
│  Withdrawable Balance                       │
│       ↓                                     │
│  24-Hour Withdrawal Control                 │
│                                             │
└─────────────────────────────────────────────┘
```

### Key Engineering Concepts

- ⚙️ Backend API design
- 🐍 Python & FastAPI
- 🗄️ PostgreSQL database design
- 🧩 SQLAlchemy ORM
- 🔄 Alembic migrations
- 💰 Financial business logic
- 🔁 Idempotency
- 🧾 Reconciliation workflows
- ♻️ Failure recovery
- 🧮 Decimal currency handling
- 🧪 Automated testing
- 🛡️ Domain exception handling
- 🐳 Docker-based infrastructure

---

# 🚀 What This Project Demonstrates

This is more than a basic CRUD backend.

The main engineering challenge is maintaining correct financial state across:

```text
Sales
  ↓
Advance Payments
  ↓
Reconciliation
  ↓
Final Settlement
  ↓
Processor Status
  ↓
Recovery
  ↓
Withdrawal
```

The implementation therefore focuses on:

```text
Correctness
    ↓
Idempotency
    ↓
Auditability
    ↓
Recovery
    ↓
Testability
```

---

# 📋 API Documentation

For complete request/response examples and an end-to-end `curl` walkthrough:

```text
docs/api-documentation.md
```

For the complete low-level design:

```text
docs/LLD.md
```

---

# 👨‍💻 Author

<div align="center">

### Devansh Negi

**Backend / AI Engineer**

Python • FastAPI • PostgreSQL • REST APIs • AI/ML • Docker

[![GitHub](https://img.shields.io/badge/GitHub-devanshnegi88-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/devanshnegi88)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Devansh%20Negi-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/devansh-negi005)

</div>

---

<div align="center">

## 💰 Payout Management System

**Reliable payout processing with reconciliation, idempotency, and failure recovery.**

</div>
