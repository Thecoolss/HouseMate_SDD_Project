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
Decision: Use four application tables: user, task, booking, and contribution_score. User contains a unique id, a unique username, and a password hash. Tasks contain created_by, description, difficulty, due_date and assigned_to foreign keys, bookings contain resource, created_by, timestamp,  and contribution_score belongs to a user and stores a calculation-period snapshot. Each recalculation creates new ContributionScore rows rather than overwriting historical results.
Alternatives considered: 1. Store the current score directly on User — rejected because it would lose historical periods and couple analytics state to the identity record. 2. Recalculate and discard the result — rejected because users should be able to inspect previous calculation periods and Domain 2 needs persistent state. 
Consequences: The database remains small and easy to understand, historical analytics are preserved, and the ER diagram can clearly show Domain 1's operational tables and Domain 2's derived table.
