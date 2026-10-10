# HouseMate

HouseMate is a small, server-rendered household management application. Housemates can coordinate household tasks, reserve shared resources, and view contribution snapshots.

## Features

- Register and log in with a username and password.
- Create household tasks, claim pending tasks, and mark assigned tasks complete.
- Reserve shared resources and reject overlapping bookings.
- Calculate and retain contribution snapshots for a selected period.

## Architecture

The application runs as one Flask process and persists data in SQLite.

- **Domain 1 — Household coordination** owns task and booking operations, including their validation and authorization rules.
- **Domain 2 — Contribution analytics** calculates and persists contribution snapshots.
- Domain 2 obtains completed-task, booking, and overdue-task data through functions exposed by Domain 1 services. This is the current modular seam between the domains.
- Flask routes translate HTTP requests into service calls; SQLAlchemy models represent the persisted data.
- `User` is shared identity, created through `app/auth`. Domain 2 reads it only to list household members and show usernames.

### Architecture diagram

```mermaid
flowchart TB
    browser["Browser<br/>(server-rendered HTML forms)"]

    subgraph process["Single Flask process: python app.py (create_app, 0.0.0.0:PORT)"]
        direction TB

        subgraph routes["HTTP layer: blueprints"]
            auth_routes["auth/routes.py<br/>/register, /login, /logout"]
            d1_routes["domain1/routes.py<br/>/tasks, /bookings"]
            d2_routes["domain2/routes.py<br/>/fairness, /fairness/recalculate"]
        end

        time_utils["time_utils.py<br/>local time to UTC conversion"]

        subgraph d1["Domain 1: Household coordination"]
            d1_services["domain1/services.py<br/>create_task, claim_task, mark_complete,<br/>create_booking, update_booking, ..."]
            d1_rules["domain1/rules.py<br/>validate_title, validate_difficulty,<br/>validate_booking"]
        end

        subgraph d2["Domain 2: Contribution analytics"]
            d2_services["domain2/services.py<br/>calculate_fairness"]
            d2_calc["domain2/calculations.py<br/>task_weight,<br/>calculate_contribution_percentages"]
        end

        subgraph models["models/ (Flask-SQLAlchemy)"]
            user_model["User"]
            task_model["Task"]
            booking_model["Booking"]
            score_model["ContributionScore"]
        end
    end

    sqlite[("SQLite<br/>DATA_DIR/app.db")]

    browser -->|"HTTP + session cookie + CSRF token"| routes
    auth_routes --> user_model
    d1_routes --> time_utils
    d1_routes -->|"usernames for display"| user_model
    d1_routes --> d1_services
    d1_services --> d1_rules
    d1_services --> task_model
    d1_services --> booking_model
    d2_routes --> d2_services
    d2_routes -->|"latest snapshot per user"| score_model
    d2_services --> d2_calc
    d2_services -->|"list household members"| user_model
    d2_services --> score_model
    d2_services ==>|"SERVICE SEAM<br/>get_completed_task_contributions<br/>get_booking_contributions<br/>get_overdue_task_counts"| d1_services
    models --> sqlite
```

Domain 2 never queries `Task` or `Booking` directly. It receives plain dictionaries from the three seam functions in `domain1/services.py`. If the domains are split into separate services later, those function calls are where HTTP calls would go.

### Database diagram

The database contains four tables. Domain 1 owns `task` and `booking`, Domain 2 owns `contribution_score`, and `user` is shared identity.

```mermaid
erDiagram
    user ||--o{ task : "creates (created_by)"
    user |o--o{ task : "is assigned (assigned_to)"
    user ||--o{ booking : "creates (created_by)"
    user ||--o{ contribution_score : "has snapshots (user_id)"

    user {
        INTEGER id PK
        VARCHAR username UK "80 chars, NOT NULL"
        VARCHAR password_hash "255 chars, NOT NULL"
    }

    task {
        INTEGER id PK
        VARCHAR title "200 chars, NOT NULL"
        TEXT description "NULL"
        VARCHAR difficulty "20 chars, NOT NULL, easy/medium/hard"
        VARCHAR status "20 chars, NOT NULL, pending/done"
        INTEGER assigned_to FK "NULL, user.id"
        INTEGER created_by FK "NOT NULL, user.id"
        DATETIME due_date "NULL, stored in UTC"
        DATETIME created_at "NOT NULL, UTC"
        DATETIME completed_at "NULL, UTC"
    }

    booking {
        INTEGER id PK
        VARCHAR resource "120 chars, NOT NULL, laundry/kitchen/living_room"
        DATETIME start_time "NOT NULL, UTC"
        DATETIME end_time "NOT NULL, UTC"
        INTEGER created_by FK "NOT NULL, user.id"
        DATETIME created_at "NOT NULL, UTC"
    }

    contribution_score {
        INTEGER id PK
        INTEGER user_id FK "NOT NULL, user.id"
        DATE period_start "NOT NULL"
        DATE period_end "NOT NULL"
        INTEGER tasks_completed "NOT NULL"
        FLOAT weighted_score "NOT NULL"
        INTEGER bookings_count "NOT NULL"
        INTEGER overdue_tasks "NULL"
        FLOAT contribution_score "NOT NULL"
        DATETIME calculated_at "NOT NULL, UTC"
    }
```

`difficulty` and `status` are enforced by SQLite `CHECK` constraints (`ck_task_difficulty`, `ck_task_status`). The allowed `resource` values are enforced in `domain1/rules.py`, not in the database. The models declare no SQLAlchemy relationship properties; the links above are the foreign-key columns only.

## Task lifecycle

An unassigned task has `status="pending"` and no `assigned_to` user. Claiming it sets `assigned_to` while it remains pending. Completing it changes its status to `"done"` and records `completed_at`.

## Contribution calculation

Completed tasks contribute points according to difficulty: easy = 1, medium = 2, hard = 3. A booking whose start time falls within the calculation period contributes one point to its creator. Each user's contribution percentage is their points divided by the household total, multiplied by 100. If the household has no points in the period, each user's percentage is zero. Overdue assigned tasks are counted separately and do not reduce the contribution percentage. Each calculation adds a new historical snapshot.

## Requirements

- Python 3.11 or newer
- Packages listed in the root `requirements.txt`
- Docker, only if you run the app in a container

## Setup

Clone the repository and enter its directory:

```bash
git clone https://github.com/Thecoolss/HouseMate_SDD_Project.git
cd HouseMate_SDD_Project
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Debian or Ubuntu, if `python3 -m venv` reports that `ensurepip` is not available, install the venv module first (for example `sudo apt install python3.11-venv`, matching your Python version).

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Set environment variables to change application settings without editing source code. These are every setting the application reads. The Docker image sets its own defaults for `PORT` and `DATA_DIR` (the values the provided container template requires).

| Variable | Default (`python app.py`) | Default (Docker image) | Purpose |
| --- | --- | --- | --- |
| `PORT` | `5000` | `8000` | Port the server listens on. |
| `DATA_DIR` | `./data` | `/data` | Directory where the SQLite database `app.db` is stored. The directory is created if needed. |
| `SECRET_KEY` | `dev-secret` | `dev-secret` | Flask session and CSRF signing key. Set a private, strong value outside local development. |
| `HOUSEHOLD_TIMEZONE` | `Europe/Paris` | `Europe/Paris` | Timezone used to interpret and display household date-times. |

**SQLite path:** `$DATA_DIR/app.db`, so `./data/app.db` when run directly and `/data/app.db` in the container. The schema is created automatically on first start (`db.create_all()`), which only creates missing tables and never drops or changes existing data. There is no seed data.

For example, on Linux or macOS:

```bash
export SECRET_KEY="replace-with-a-private-random-value"
export DATA_DIR="./data"
export HOUSEHOLD_TIMEZONE="Europe/Paris"
```

The default secret key is for local development only.

## Run

### Directly on a machine

From the repository root, after the setup steps above, start the application with:

```bash
python app.py
```

The application binds to `0.0.0.0` and defaults to port `5000`. Open <http://localhost:5000/register> to register the first user.

### With Docker

The `Dockerfile` at the repository root is the provided course template with its four `TODO` lines filled in: `python:3.12-slim`, `pip install -r requirements.txt`, an explicit copy of `app.py`, `config.py`, and `app/`, and `python app.py` as the start command. Tests, the virtual environment, `.git`, and local data are not copied into the image.

Build the image and run it with a named volume for the database:

```bash
docker build -t housemate .
docker run -p 8000:8000 -v housemate-data:/data housemate
```

Open <http://localhost:8000/register>. The database lives in the `housemate-data` volume at `/data/app.db`, so it survives the container being removed and recreated.

To use another port or set a real secret key:

```bash
docker run -e PORT=9000 -p 9000:9000 -e SECRET_KEY="replace-with-a-private-random-value" -v housemate-data:/data housemate
```

### Container contract evidence (§7)

Output of the provided checker, `container/run.sh`, run against this repository on 2026-10-10:

```text
=== SDD Assignment 1 contract check ===
Repository: /home/coolss/Uni_Projects/sdd/House_Project
==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)
==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 60 MB
==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 302 from http://localhost:8000/
==> SQLite file under DATA_DIR
  PASS  found in /data: app.db 
==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: booking=0 contribution_score=0 task=0 user=0 
==> PORT override is honoured (not hardcoded)
  PASS  HTTP 302 from http://localhost:9123/
=== ALL CHECKS PASSED ===

```

`HTTP 302` is expected: `/` redirects anonymous users to `/login`.

When running the checker from WSL, set `NAME` explicitly (for example `NAME=sdd-housemate ./run.sh .`), because WSL sets `NAME` to the Windows host name, which is not a valid image tag.

## Tests and coverage

Run the test suite:

```bash
pytest
```

Coverage is reported two ways: for the complete application, and for the core business logic of the two domains, which is what the 70% target applies to.

### Whole-application coverage

```bash
pytest --cov=app --cov-report=term-missing
```

**Measured on 2026-10-09:** 65 tests passed; whole-application coverage was **72%**. This figure also counts Flask routes, app setup, and the timezone helpers in `app/time_utils.py`.

### Core business-logic coverage (Domain 1 and Domain 2)

```bash
pytest \
  --cov=app.domain1.services \
  --cov=app.domain1.rules \
  --cov=app.domain2.services \
  --cov=app.domain2.calculations \
  --cov-report=term-missing
```

**Measured on 2026-10-09:** 65 tests passed, with **93% combined coverage** across these four modules.

Coverage can change as the code and tests change; rerun both commands before submitting and update these results if they differ.

## Project structure

```text
app/
  auth/        Registration, login, and logout routes
  domain1/     Task and booking routes, services, and pure validation rules
  domain2/     Contribution routes, calculation services, and pure calculations
  models/      SQLAlchemy models for the four SQLite tables
  templates/   Server-rendered HTML templates
  static/      CSS
tests/
  unit/        Isolated tests for pure validation, calculation, and timezone functions
  test_*.py    Database-backed service tests and Flask authentication tests
app.py         Entry point: python app.py
config.py      Environment-variable configuration
Dockerfile     Provided container template with its four TODOs filled in
requirements.txt  Pinned dependencies (the one manifest)
ADR.md         Architecture decision record log
AI_USAGE.md    Log of meaningful AI-assisted work
```
