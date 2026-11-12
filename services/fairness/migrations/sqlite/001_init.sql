-- Fairness initial schema (SQLite, used by the test suite). user_id is a plain
-- integer, not a foreign key: the user lives in the household service's database,
-- so integrity across the seam is enforced in code (ADR-6, ADR-7).

CREATE TABLE contribution_score (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    period_start       DATE NOT NULL,
    period_end         DATE NOT NULL,
    tasks_completed    INTEGER NOT NULL,
    weighted_score     FLOAT NOT NULL,
    bookings_count     INTEGER NOT NULL,
    overdue_tasks      INTEGER NULL,
    contribution_score FLOAT NOT NULL,
    calculated_at      DATETIME NOT NULL
);
