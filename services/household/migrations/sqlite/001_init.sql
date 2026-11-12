-- Household initial schema (SQLite, used by the test suite). Same tables and
-- constraints as the SQL Server version, in SQLite dialect. "user" is quoted
-- because it is otherwise a reserved word.

CREATE TABLE "user" (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE task (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        VARCHAR(200) NOT NULL,
    description  TEXT NULL,
    difficulty   VARCHAR(20)  NOT NULL CONSTRAINT ck_task_difficulty
                     CHECK (difficulty IN ('easy', 'medium', 'hard')),
    status       VARCHAR(20)  NOT NULL CONSTRAINT ck_task_status
                     CHECK (status IN ('pending', 'done')),
    assigned_to  INTEGER NULL     REFERENCES "user"(id),
    created_by   INTEGER NOT NULL REFERENCES "user"(id),
    due_date     DATETIME NULL,
    created_at   DATETIME NOT NULL,
    completed_at DATETIME NULL
);

CREATE TABLE booking (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    resource   VARCHAR(120) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time   DATETIME NOT NULL,
    created_by INTEGER NOT NULL REFERENCES "user"(id),
    created_at DATETIME NOT NULL
);
