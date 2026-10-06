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

The database contains four tables:

- `user`: username and password hash.
- `task`: creator, optional assignee and due date, difficulty, status, and completion time.
- `booking`: resource, start and end times, and creator.
- `contribution_score`: per-user calculation-period metrics and calculation timestamp.

## Task lifecycle

An unassigned task has `status="pending"` and no `assigned_to` user. Claiming it sets `assigned_to` while it remains pending. Completing it changes its status to `"done"` and records `completed_at`.

## Contribution calculation

Completed tasks contribute points according to difficulty: easy = 1, medium = 2, hard = 3. A booking whose start time falls within the calculation period contributes one point to its creator. Each user's contribution percentage is their points divided by the household total, multiplied by 100. If the household has no points in the period, each user's percentage is zero. Overdue assigned tasks are counted separately and do not reduce the contribution percentage. Each calculation adds a new historical snapshot.

## Requirements

- Python 3.11 or newer
- Packages listed in the root `requirements.txt`

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

On Windows PowerShell, activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Set environment variables to change application settings without editing source code.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `5000` | Port used by the Flask development server. |
| `DATA_DIR` | `./data` | Directory where the SQLite database `app.db` is stored. The directory is created if needed. |
| `SECRET_KEY` | `dev-secret` | Flask session and CSRF signing key. Set a private, strong value outside local development. |
| `HOUSEHOLD_TIMEZONE` | `Europe/Paris` | Timezone used to interpret and display household date-times. |

For example, on Linux or macOS:

```bash
export SECRET_KEY="replace-with-a-private-random-value"
export DATA_DIR="./data"
export HOUSEHOLD_TIMEZONE="Europe/Paris"
```

The default secret key is for local development only.

## Run

From the repository root, start the application with:

```bash
python app.py
```

The application binds to `0.0.0.0` and defaults to port `5000`. Open <http://localhost:5000/register> to register the first user.

## Tests and coverage

Run the test suite:

```bash
pytest
```

Measure coverage across the complete application:

```bash
pytest --cov=app --cov-report=term-missing
```

**Measured on 2026-10-06:** 50 tests passed; whole-application coverage was **69%**. This includes Flask routes and timezone utilities as well as business logic, and is below 70% if the target is interpreted as whole-application coverage.

The assignment's coverage requirement specifically concerns the core business logic. To measure the domain service and pure-rule modules:

```bash
pytest \
  --cov=app.domain1.services \
  --cov=app.domain1.rules \
  --cov=app.domain2.services \
  --cov=app.domain2.calculations \
  --cov-report=term-missing
```

**Measured on 2026-10-06:** the 50-test suite passed, with **93% combined coverage** across these four modules. Coverage can change as the code and tests change; rerun the command before submitting and update these results if they differ.

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
  unit/        Isolated tests for pure validation and calculation functions
  test_*.py    Database-backed service tests and Flask authentication tests
ADR.md         Architecture decision record log
AI_USAGE.md   Log of meaningful AI-assisted work
```
