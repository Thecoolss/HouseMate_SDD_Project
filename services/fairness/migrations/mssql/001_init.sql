-- Fairness initial schema (SQL Server). Matches the ContributionScore model.
-- user_id is a plain INT, not a foreign key: the user lives in the household
-- service's database, so integrity across the seam is enforced in code (ADR-6, ADR-7).

IF OBJECT_ID(N'contribution_score', N'U') IS NULL
CREATE TABLE contribution_score (
    id                 INT IDENTITY(1,1) PRIMARY KEY,
    user_id            INT NOT NULL,
    period_start       DATE NOT NULL,
    period_end         DATE NOT NULL,
    tasks_completed    INT NOT NULL,
    weighted_score     FLOAT NOT NULL,
    bookings_count     INT NOT NULL,
    overdue_tasks      INT NULL,
    contribution_score FLOAT NOT NULL,
    calculated_at      DATETIME2 NOT NULL
);
GO
