# 💰 Payout Management System

> **A backend payout and reconciliation platform for affiliate sales, supporting advance payouts, final settlement, withdrawal controls, idempotent processing, and failed-payout recovery.**

<div align="center">

**FastAPI • PostgreSQL • SQLAlchemy • Alembic • Pydantic • Pytest**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-499848)](https://alembic.sqlalchemy.org/)
[![Pytest](https://img.shields.io/badge/Pytest-Testing-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)

</div>

---

# 📌 Overview

The **Payout Management System** is a backend service designed to manage the complete payout lifecycle for affiliate sales.

Each affiliate sale begins in a **Pending** state. The system can immediately issue an **advance payout of 10%** of the sale's earnings. Later, an administrator reconciles the sale as either **Approved** or **Rejected**, after which the system calculates the final payout while accounting for any advance that has already been paid.

The system also handles:

- 💸 Advance payouts
- 🧾 Final reconciliation payouts
- 🔁 Idempotent payout processing
- ⏱️ 24-hour withdrawal cooldowns
- ♻️ Failed payout recovery
- 💰 Withdrawable balance management
- 📒 Auditable payout ledger
- 🔐 Domain-specific validation
- 🧪 Comprehensive business-rule testing

---

# 💼 Business Problem

The payout lifecycle can be summarized as:

```text
Affiliate Sale
      │
      ▼
   Pending
      │
      ├───────────────┐
      │               │
      ▼               ▼
10% Advance       Reconciliation
Payout                 │
                       ▼
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
           Approved          Rejected
              │                 │
              ▼                 ▼
       Final Settlement      Clawback
```

The system ensures that the advance payment is correctly accounted for when the final settlement occurs.

---

# 💰 Core Business Rules

## 1. Advance Payout

A user receives:

```text
Advance = 10% × Pending Sale Earnings
```

The advance can be paid **at most once per sale**.

The `advance_paid` amount acts as the idempotency anchor, making the operation safe even if the payout job runs multiple times.

---

## 2. Final Payout

### Approved Sale

```text
Final Payout = Earnings − Advance Paid
```

### Rejected Sale

```text
Final Payout = −Advance Paid
```

The negative amount represents a **clawback**, because the user was not ultimately entitled to the advance.

---

## 3. Withdrawal Restriction

Each user can make:

```text
1 withdrawal / 24 hours
```

The cooldown is enforced by the service layer.

---

## 4. Failed Payout Recovery

If a payout enters one of these states:

```text
cancelled
rejected
failed
```

the corresponding amount is credited back to the user's **withdrawable balance**.

This allows the user to retry the payout without permanently losing funds.

---

# 🏗️ Architecture

The project uses a deliberately simple **layered architecture**:

```text
┌──────────────────────────────┐
│          HTTP Layer          │
│      FastAPI Routes          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Service Layer          │
│                              │
│ • Advance Payout             │
│ • Reconciliation             │
│ • Withdrawal                 │
│ • Recovery                   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│        ORM / Models          │
│         SQLAlchemy           │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         PostgreSQL           │
└──────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| `routes/` | HTTP request/response handling |
| `services/` | Business rules and domain workflows |
| `models/` | SQLAlchemy database entities |
| `schemas/` | Pydantic request/response contracts |
| `utils/` | Domain-specific exception hierarchy |
| `database.py` | Database engine, sessions, and declarative base |
| `config.py` | Application configuration |

---

# 🧠 Why Layered Architecture?

The system intentionally avoids introducing unnecessary architectural complexity.

Patterns such as:

- Clean Architecture
- Hexagonal Architecture
- Repository interfaces
- Dedicated use-case classes
- Dependency-injection containers

can be useful in larger systems, but would introduce additional ceremony for this assignment.

The selected architecture keeps the system:

> **Simple enough to understand, while still demonstrating strong separation of concerns.**

The `core/` package was also intentionally avoided because the current project does not contain enough cross-cutting infrastructure to justify another abstraction layer.

---

# 🔄 End-to-End Payout Flow

```text
                 Create Sale
                      │
                      ▼
                 ┌─────────┐
                 │ Pending │
                 └────┬────┘
                      │
                      ▼
             Advance Payout Job
                      │
                      ▼
              10% of Earnings
                      │
                      ▼
              Advance Recorded
                      │
                      ▼
               Admin Reconcile
                      │
              ┌───────┴───────┐
              │               │
              ▼               ▼
           Approved         Rejected
              │               │
              ▼               ▼
        Earning - Advance  -Advance
              │               │
              └───────┬───────┘
                      ▼
                Final Payout
                      │
                      ▼
              Payout Ledger
```

---

# 🗄️ Database Design

The system revolves around three primary entities.

## 👤 User

Stores:

- User identity
- Withdrawable balance

---

## 🛒 Sale

Represents an affiliate sale.

Important fields include:

- Sale status
- Earnings
- Advance-paid amount

The `advance_paid` amount is also the key idempotency anchor for advance processing.

---

## 💸 Payout

Represents every payout event.

Supported payout lifecycle states include:

```text
pending
completed
failed
cancelled
rejected
```

A payout can represent:

- Advance payout
- Final payout
- Withdrawal

This creates a centralized, auditable payout history and enables recovery workflows.

---

# 📊 Data Model

```text
┌────────────────────┐
│       User         │
├────────────────────┤
│ id                 │
│ withdrawable_bal.  │
└─────────┬──────────┘
          │
          │ 1:N
          ▼
┌────────────────────┐
│       Sale         │
├────────────────────┤
│ id                 │
│ user_id            │
│ status              │
│ earning             │
│ advance_paid        │
└─────────┬──────────┘
          │
          │
          ▼
┌────────────────────┐
│      Payout        │
├────────────────────┤
│ id                 │
│ user_id            │
│ sale_id             │
│ type                │
│ amount              │
│ status              │
└────────────────────┘
```

For the complete schema, ER diagram, indexes, and relationships, see:

`docs/database-schema.md`

---

# 📁 Project Structure

```text
payout-management-system/
│
├── app/
│   ├── main.py
│   │
│   ├── database.py
│   │
│   ├── config.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── sale.py
│   │   └── payout.py
│   │
│   ├── schemas/
│   │   └── ...
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
│       └── exceptions.py
│
├── alembic/
│   └── ...
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
| `POST` | `/sales` | Create a sale |
| `GET` | `/sales/{sale_id}` | Fetch a sale |
| `GET` | `/sales?user_id=...` | List user sales |
| `PATCH` | `/sales/{sale_id}/reconcile` | Reconcile a sale |
| `POST` | `/sales/reconcile/batch` | Batch reconciliation |
| `POST` | `/payouts/advance/{user_id}` | Run advance payout for one user |
| `POST` | `/payouts/advance` | Run advance payout for all users |
| `GET` | `/payouts?user_id=...` | Fetch payout ledger |
| `PATCH` | `/payouts/{payout_id}/status` | Simulate processor callback |
| `POST` | `/payouts/recover/{user_id}` | Run recovery sweep |
| `POST` | `/withdrawals/{user_id}` | Withdraw full balance |
| `GET` | `/health` | Liveness check |

---

# 🔁 Advance Payout Processing

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

If the same advance job executes again:

```text
First Run
   │
   ├── Advance created
   └── advance_paid updated

Second Run
   │
   └── Already paid → Skip
```

This protects against duplicate payouts when scheduled jobs are retried or rerun.

---

# 🧾 Reconciliation

The reconciliation process supports:

```text
Pending
   │
   ├───────────────┐
   ▼               ▼
Approved        Rejected
   │               │
   ▼               ▼
earning -       -advance
advance_paid      paid
```

Reconciliation is designed to be idempotent, preventing the same sale from being financially settled multiple times.

---

# 🔄 Payout Recovery

Processor callbacks can transition payouts into failure states.

```text
Payout
  │
  ▼
Processor Callback
  │
  ├── completed ──► No recovery
  │
  ├── failed ─────► Credit balance
  │
  ├── cancelled ──► Credit balance
  │
  └── rejected ───► Credit balance
```

A manual recovery endpoint is also available for missed callbacks:

```http
POST /payouts/recover/{user_id}
```

Recovery is itself designed to be idempotent.

---

# ⏱️ Withdrawal Cooldown

A user can withdraw their available balance only once within a 24-hour period.

```text
Withdrawal Request
        │
        ▼
Check Previous Withdrawal
        │
        ▼
   Within 24 hours?
      │       │
     Yes      No
      │        │
      ▼        ▼
   Reject    Allow
               │
               ▼
        Withdraw Balance
```

The system also considers the interaction between **withdrawal cooldown and payout recovery**, preventing recovery logic from bypassing the intended withdrawal restrictions.

---

# 🧮 Financial Precision

Financial calculations use **Decimal-based arithmetic** rather than floating-point calculations.

This is particularly important for:

- Advance calculations
- Final payout calculations
- Clawbacks
- Withdrawals
- Balance updates
- Currency rounding

Example:

```text
Sale Earnings = ₹120

Advance = 10%

Advance = ₹120 × 0.10
        = ₹12
```

The reconciliation tests also cover the complete **₹68 worked example** from the assignment.

---

# 🧪 Testing

The project uses **pytest** with an **in-memory SQLite database** for the test suite.

This means:

> PostgreSQL is not required to execute the automated tests.

Run:

```bash
pytest tests/ -v
```

---

# ✅ Test Coverage

### `test_advance_payout.py`

Covers:

- 10% calculation
- ₹120 → ₹12 example
- Advance payout creation
- Idempotent reruns

### `test_reconciliation.py`

Covers:

- Approved payout calculation
- Rejected payout calculation
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
- Credit-back behavior
- Recovery idempotency

---

# ⚠️ Edge Cases

The implementation explicitly handles **13 edge and failure scenarios**.

These include:

- Duplicate advance payout execution
- Double reconciliation
- Withdrawal cooldown enforcement
- Recovery after failed payouts
- Missed processor callbacks
- Recovery sweeps
- Interaction between recovery and withdrawal cooldown
- Currency rounding safety

Detailed reasoning and test references are available in:

`docs/edge-cases.md`

---

# ⚙️ Setup

## Prerequisites

- Python **3.11+**
- PostgreSQL
- `pip`
- Virtual environment

---

## 1. Clone Repository

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

Update `.env` with the PostgreSQL connection details.

---

## 5. Run Migrations

```bash
alembic upgrade head
```

---

## 6. Start Server

```bash
uvicorn app.main:app --reload
```

Application:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 🐘 PostgreSQL with Docker

If PostgreSQL is not installed locally:

```bash
docker run --name payout-db \
  -e POSTGRES_USER=payout_user \
  -e POSTGRES_PASSWORD=payout_password \
  -e POSTGRES_DB=payout_management \
  -p 5432:5432 \
  -d postgres
```

The default `.env.example` configuration is designed to match this setup.

---

# 🛠️ Technology Stack

| Category | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Validation | Pydantic |
| Migrations | Alembic |
| Testing | Pytest |
| Test Database | SQLite |
| Configuration | Pydantic BaseSettings |
| Containerization | Docker |

---

# 📚 Documentation

The project includes dedicated engineering documentation.

| Document | Covers |
|---|---|
| `docs/LLD.md` | Overall workflow, entity responsibilities, business rules |
| `docs/database-schema.md` | ER diagram, columns, indexes, relationships |
| `docs/class-design.md` | Models, services, schemas, exception hierarchy |
| `docs/api-documentation.md` | API endpoints and request/response examples |
| `docs/edge-cases.md` | 13 edge cases and test references |
| `docs/design-decisions.md` | Architectural decisions and trade-offs |

---

# 🧠 Design Decisions

Several deliberate engineering decisions shape the implementation.

### Single Payout Ledger

A single `Payout` entity records:

- Advance payouts
- Final payouts
- Withdrawals

This creates a centralized financial history.

### Stateless Services

Business logic is implemented through service functions rather than stateful service classes.

### Decimal Currency Handling

Financial calculations use Decimal arithmetic to avoid floating-point precision issues.

### Idempotent Operations

Advance payouts, reconciliation, and recovery are designed to safely handle repeated execution.

### Non-Atomic Batch Reconciliation

Batch reconciliation is intentionally not treated as one all-or-nothing transaction, allowing individual sale outcomes to be processed independently.

### Simple Architecture

The system avoids abstraction layers that do not provide meaningful value at this project scale.

---

# 📈 Engineering Highlights

```text
┌─────────────────────────────────────────────┐
│             PAYOUT ENGINE                   │
├─────────────────────────────────────────────┤
│                                             │
│  10% Advance Payout                         │
│          ↓                                  │
│  Idempotent Processing                      │
│          ↓                                  │
│  Admin Reconciliation                       │
│          ↓                                  │
│  Approved / Rejected Settlement             │
│          ↓                                  │
│  Payout Ledger                              │
│          ↓                                  │
│  Processor Failure Recovery                 │
│          ↓                                  │
│  Withdrawable Balance                       │
│          ↓                                  │
│  24-Hour Withdrawal Control                 │
│                                             │
└─────────────────────────────────────────────┘
```

### Key Engineering Concepts Demonstrated

- Backend API design
- Layered architecture
- Financial business logic
- Idempotency
- Reconciliation workflows
- Failure recovery
- Database modeling
- Transaction-aware domain logic
- Decimal currency calculations
- API validation
- Exception handling
- Database migrations
- Automated testing
- Dockerized infrastructure

---

# 🚀 What This Project Demonstrates

This project is designed around a realistic financial workflow rather than a simple CRUD API.

The core challenge is maintaining a correct financial state across:

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

The implementation therefore focuses heavily on:

**correctness → idempotency → auditability → recovery → testability**

---

# 👨‍💻 Author

**Devansh Negi**

Backend / AI Engineer focused on:

- ⚙️ Backend Engineering
- 🐍 Python & FastAPI
- 🗄️ PostgreSQL & Database Design
- 🔌 REST APIs
- 🤖 AI/ML Applications
- 🐳 Docker & Deployment
- 🧪 Software Testing

### Connect

- **GitHub:** https://github.com/devanshnegi88
- **LinkedIn:** https://linkedin.com/in/devansh-negi005

---

<div align="center">

## 💰 Payout Management System

**Reliable payout processing with reconciliation, idempotency, and failure recovery.**

</div>
