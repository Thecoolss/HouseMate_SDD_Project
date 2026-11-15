## 1. Backend language and framework
Date: 2026-09-21
Status: Superseded by [6]
Context: The application must run as a single process and container, use SQLite for persistence, support simple session-based authentication, provide CRUD operations, and expose business logic that can be unit tested independently of HTTP routes. This makes the framework choice less about raw feature count and more about keeping the stack small, explicit, and easy to reason about while still supporting the required app lifecycle.
Decision: Use Python because I am already comfortable with it and have built projects with it in the past, with  Flask, Flask-SQLAlchemy, Flask-Login, and Flask-WTF. Flask fits this project because it keeps the footprint small, avoids imposing a large built-in framework surface, and gives us explicit control over application structure, database setup, user sessions, and route-level logic without adding unnecessary complexity for a monolithic household-management app.
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
Status: Superseded by [7]
Context: Domain 1 requires persistent operational state for users, tasks, and bookings, while Domain 2 needs its own persisted output so historical calculations can be viewed later. Task ownership and assignment also need to be represented explicitly for authorization and contribution attribution.
Decision: Use four tables, user, task, booking, and contribution_score, where task references user through created_by and assigned_to, booking through created_by, and contribution_score through user_id. Each recalculation appends one new contribution_score row per user for the period, including an overdue_tasks count that is reported separately and does not reduce the contribution percentage, rather than overwriting earlier snapshots.
Alternatives considered: 1. Store the current score directly on User — rejected because it would lose historical periods and couple analytics state to the identity record. 2. Recalculate and discard the result — rejected because users should be able to inspect previous calculation periods and Domain 2 needs persistent state. 
Consequences: The database remains small and easy to understand, historical analytics are preserved, and the ER diagram can clearly show Domain 1's operational tables and Domain 2's derived table. (Revised 2026-10-01: the overdue_tasks column and overdue reporting were added to this decision when overdue tracking was introduced.)

## 4. Testing approach
Date: 2026-10-02
Status: Superseded by [9]
Context: The assignment requires at least 70% coverage of the core business logic. The most important correctness risks are authorization, task state transitions, booking conflicts, and contribution calculations.
Decision: Prioritize SQLite-backed integration tests of the Domain 1 and Domain 2 service functions, plus isolated unit tests of the pure validation and calculation functions in domain1/rules.py and domain2/calculations.py. Route tests are limited to authentication; the task, booking, and contribution routes and templates are deliberately left thinner because they only translate HTTP requests into service calls.
Alternatives considered: 1. Primarily browser/end-to-end testing — rejected because it is slower, harder to isolate business rules, and does not directly target the required core-logic coverage. 2. Testing every route/template exhaustively — rejected because the highest-risk behavior is in service-layer rules and calculations.
Consequences: The four business-logic modules reach 93% coverage, so authorization, task-state, booking-conflict, and scoring rules are easy to regression-test, while domain1/routes.py stays around 29% and the whole app around 72%. Presentation-layer regressions in routes and templates still need manual verification. (Revised 2026-10-04: pure functions were moved into rules.py and calculations.py so they could be unit-tested without a database.)

## 5. Deliberately not building notifications
Date: 2026-10-09
Status: Decided
Context: A household application could notify users about claimed tasks, approaching deadlines, overdue tasks, or upcoming bookings. Implementing this fully would introduce additional infrastructure and increase the project's scope beyond the two required domains.
Decision: Do not implement notifications in Assignment 1. Keep the application focused on household coordination and contribution analytics; overdue tasks are surfaced only as a count on the contribution page when a user recalculates.
Alternatives considered: 1. Email notifications — rejected because they need an external mail service and extra configuration, which conflicts with having no required external runtime dependency. 2. Background notification workers or scheduled jobs — rejected because background job runners and additional processes are out of scope for the single-process, single-container deployment contract. 3. In-app notifications stored in SQLite — rejected because they would add a new table, UI, and read/unread state without being necessary for either required domain.
Consequences: The application stays small and compatible with the single-process deployment contract, but users must open the app to see claimed, overdue, or upcoming items. Notifications remain possible future work, for example as a separate service once the domains are split in a later assignment.

## 6. Splitting the monolith into two services along the ADR-2 seam
Date: 2026-11-08
Status: Decided
Context: Assignment 2 requires separate processes and databases for the two domains while preserving the Assignment 1 use case. ADR-2 already separates household operations from contribution analytics.
Decision: Keep the ADR-2 seam: household owns users, authentication, tasks and bookings, while fairness owns contribution snapshots and requests member and contribution data over HTTP. Keep Flask and SQLAlchemy, replacing server-rendered pages and session authentication with static HTML/JavaScript and signed bearer tokens that fairness verifies locally and forwards to household.
Alternatives considered: A shared database would retain cross-domain coupling and violate database ownership; copying operational rows into fairness would introduce synchronization work without a current need.
Consequences: Household remains usable without fairness, and fairness serves saved snapshots without names when household is unavailable. Recalculation depends on household and returns a clear 503 after a bounded failed HTTP call rather than writing partial results.

## 7. Data per service, versioned migrations, and recovery
Date: 2026-11-12
Status: Decided
Context: The monolith used one SQLite database and created its schema on startup. Separate service databases require explicit schema ownership and a way to evolve populated tables without losing rows.
Decision: Start with fresh service databases rather than import the Assignment 1 development data, assigning user/task/booking to household and contribution_score to fairness. Define each schema with numbered SQL migrations applied at startup and recorded in schema_migrations; contribution_score.user_id becomes a plain ID populated from household's HTTP member list.
Alternatives considered: Alembic would provide more migration tooling but adds concepts beyond this small schema; importing the development database was unnecessary because its rows were disposable test data.
Consequences: Rows survive restarts and future migrations, but a snapshot can outlive its household user because SQL cannot enforce the cross-service reference. On SQL Server a failing migration transaction rolls back and startup fails: repair an unapplied failing file before retrying, or correct an already-applied migration with a higher-numbered file, never by editing the applied file; SQLite DDL rollback is more limited.

## 8. Serverless hosting on a personal Azure subscription
Date: 2026-11-15
Status: Decided
Context: Updated course instructions require a personal subscription, managed identity and Storage-hosted UI. This subscription forbids France Central, so HouseMate uses Germany West Central in its own resource group.
Decision: Use Azure CLI scripts to provision rg-sdroubi-ieu2024 with a Consumption environment for two apps (0–1 replicas each), two isolated General Purpose serverless SQL databases (0.5–1 vCore, 2 GB, currently 15-minute idle auto-pause), a Storage static website, usage-billed Log Analytics and a deployment identity. Use public SHA-tagged GHCR images, main-only GitHub OIDC with resource-group-scoped permissions, and Container Apps secret references for runtime credentials.
Alternatives considered: Bicep was deferred in favour of understandable CLI scripts; and always-on compute would conflict with the assignment's serverless requirement.
Consequences: Containers and SQL can sleep, so startup migrations must tolerate database resume through bounded connection retries, suitable worker/probe/request timeouts and closed idle connections; storage, backups and logs may still consume credit. At 100x traffic, the one-worker, one-replica services and the 1-vCore databases become the limits, so we would add threads and replicas and move migrations into a deploy step (or a SQL application lock), since several replicas could otherwise run them at once. We would also raise the SQL capacity and add indexes on contribution_score(user_id, calculated_at) and booking(resource, start_time), store usernames with snapshots so GET /fairness stops calling household on every view, and reconsider provisioned SQL, because scale-to-zero saves nothing under constant load.

## 9. Pipeline and testing
Date: 2026-11-13
Status: Decided
Context: Every push and PR must validate both services before main can publish and deploy the same tested commit. Cross-service behaviour and SQL Server persistence require checks beyond isolated business-logic tests.
Decision: Keep one workflow whose lint, per-service 70% coverage gates, system/OpenAPI validation, HTTP integration and SQL Server Compose smoke checks must pass before image builds, with SHA-tagged publication and dependent Azure deployment only on pushes to main. Test the seam using real service processes with separate SQLite databases, and verify SQL Server migrations, restart persistence and partial failure with the Compose smoke test; CD checks the expected health SHA before publishing the UI.
Alternatives considered: A separate CD workflow would need explicit coordination to select the successful CI commit; a stub-only seam test could agree with an outdated contract, while full browser tests add maintenance beyond the current service-focused checks.
Consequences: Failed checks block publication and deployment, and serialized deployment jobs do not cancel an active deployment mid-run. Browser interactions and actual Azure cold-start timing are not covered by automated CI, which never connects to Azure SQL; generated deployment tests check configuration rather than prove that cloud deployment succeeds.

