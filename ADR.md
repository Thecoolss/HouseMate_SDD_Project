## 1. Backend language and framework
Date: 2026-09-21
Status: Decided
Context: The application must run as a single process and container, use SQLite for persistence, support simple session-based authentication, provide CRUD operations, and expose business logic that can be unit tested independently of HTTP routes. This makes the framework choice less about raw feature count and more about keeping the stack small, explicit, and easy to reason about while still supporting the required app lifecycle.
Decision: Use Flask with Flask-SQLAlchemy, Flask-Login, and Flask-WTF. Flask fits this project because it keeps the footprint small, avoids imposing a large built-in framework surface, and gives us explicit control over application structure, database setup, user sessions, and route-level logic without adding unnecessary complexity for a monolithic household-management app.
Alternatives considered: 1. Django — rejected because the project does not require Django's larger built-in framework surface, such as its admin system or opinionated app conventions, for a small single-process CRUD application. 2. FastAPI — rejected because the application is primarily server-rendered CRUD and business logic rather than an async API-first service; asynchronous request handling is not required for the current scope.
Consequences: The application will have a small dependency set and a clear, testable architecture, but we will need to implement application-level features such as UI flow, authorization checks, and session handling ourselves rather than relying on a larger framework to provide them automatically.

## 2. Domain boundary: household coordination and contribution analytics
Date: 2026-09-23
Status: Decided
Context: Domain 1 manages frequently changing household state such as tasks and resource bookings. Domain 2 analyzes that operational data to produce contribution analytics and historical snapshots. Their responsibilities, data lifecycle, and future evolution are different, so they need an explicit modular boundary.
Decision: Domain 1 owns task and booking operations. Domain 2 owns contribution calculation and ContributionScore persistence. Domain 2 will consume Domain 1 information through explicit service interfaces rather than scattering direct ORM queries throughout the analytics logic.
Alternatives considered: 1. Put fairness calculation inside Domain 1 — rejected because analytics logic would become coupled to CRUD and authorization logic. 2. Recalculate analytics directly on every page request without persisted results — rejected because historical analytics are useful application data and it is not logical or feasible in the future to recompute every time a user makes a request.
Consequences: The monolith remains simple while a clear seam exists for a future service split. Domain 2 must depend on stable Domain 1 service interfaces, so those interfaces need to remain small and well defined.

## 3. SQLite data model and historical contribution snapshots
Date: 2026-09-24
Status: Decided
Context: Domain 1 requires persistent operational state for users, tasks, and bookings, while Domain 2 needs its own persisted output so historical calculations can be viewed later. Task ownership and assignment also need to be represented explicitly for authorization and contribution attribution.
Decision: Use four application tables: user, task, booking, and contribution_score. User contains a unique id, a unique username, and a password hash. Tasks contain a title, description, difficulty, status, due_date, and timestamps, plus two foreign keys to user: created_by and assigned_to; bookings contain a resource, start and end times, and a created_by foreign key to user. ContributionScore belongs to a user through its user_id foreign key and stores a calculation-period snapshot, including completed task counts, weighted contribution, booking counts, and overdue pending task counts. Positive contribution is calculated from completed task points and bookings; overdue tasks are reported separately and do not reduce contribution percentages. Each recalculation creates new ContributionScore rows rather than overwriting historical results.
Alternatives considered: 1. Store the current score directly on User — rejected because it would lose historical periods and couple analytics state to the identity record. 2. Recalculate and discard the result — rejected because users should be able to inspect previous calculation periods and Domain 2 needs persistent state. 
Consequences: The database remains small and easy to understand, historical analytics are preserved, and the ER diagram can clearly show Domain 1's operational tables and Domain 2's derived table. (Revised 2026-10-01: the overdue_tasks column and overdue reporting were added to this decision when overdue tracking was introduced.)

## 4. Testing approach
Date: 2026-10-02
Status: Decided
Context: The assignment requires at least 70% coverage of the core business logic. The most important correctness risks are authorization, task state transitions, booking conflicts, and contribution calculations.
Decision: Prioritize unit and integration tests around the Domain 1 and Domain 2 service layers. Use Flask route tests only where necessary to verify authentication/integration behavior, rather than attempting to achieve coverage through templates and framework glue.
Alternatives considered: 1. Primarily browser/end-to-end testing — rejected because it is slower, harder to isolate business rules, and does not directly target the required core-logic coverage. 2. Testing every route/template exhaustively — rejected because the highest-risk behavior is in service-layer rules and calculations.
Consequences: The core business rules should have high coverage and be easy to regression-test. Some presentation-layer regressions will still need manual verification.
