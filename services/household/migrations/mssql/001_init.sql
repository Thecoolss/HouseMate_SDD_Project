-- Household initial schema (SQL Server). Matches the User, Task and Booking models.
-- Guarded with IF OBJECT_ID so re-running during development is harmless; the
-- schema_migrations ledger is what actually stops this from running twice.

IF OBJECT_ID(N'[user]', N'U') IS NULL
CREATE TABLE [user] (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    username      NVARCHAR(80)  NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL
);
GO

IF OBJECT_ID(N'task', N'U') IS NULL
CREATE TABLE task (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    title        NVARCHAR(200) NOT NULL,
    description  NVARCHAR(MAX) NULL,
    difficulty   NVARCHAR(20)  NOT NULL CONSTRAINT ck_task_difficulty
                     CHECK (difficulty IN ('easy', 'medium', 'hard')),
    status       NVARCHAR(20)  NOT NULL CONSTRAINT ck_task_status
                     CHECK (status IN ('pending', 'done')),
    assigned_to  INT NULL     CONSTRAINT fk_task_assigned_to REFERENCES [user](id),
    created_by   INT NOT NULL CONSTRAINT fk_task_created_by  REFERENCES [user](id),
    due_date     DATETIME2 NULL,
    created_at   DATETIME2 NOT NULL,
    completed_at DATETIME2 NULL
);
GO

IF OBJECT_ID(N'booking', N'U') IS NULL
CREATE TABLE booking (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    resource   NVARCHAR(120) NOT NULL,
    start_time DATETIME2 NOT NULL,
    end_time   DATETIME2 NOT NULL,
    created_by INT NOT NULL CONSTRAINT fk_booking_created_by REFERENCES [user](id),
    created_at DATETIME2 NOT NULL
);
GO
