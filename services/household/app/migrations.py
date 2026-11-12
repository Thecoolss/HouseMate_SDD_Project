"""A tiny forward-only migration runner (Assignment 2 Â§4).

The schema is defined by numbered .sql files, not by db.create_all(). On startup the
runner applies every file that has not run yet, in order, and records each one in a
schema_migrations table so a second boot applies nothing.

The SQL dialects differ between the database this service runs on in production
(SQL Server) and the one the tests use (SQLite), so migrations live in per-dialect
folders: migrations/mssql/ and migrations/sqlite/. The runner picks the folder that
matches the engine it is connected to.

Forward-only: there are no down-migrations. A bad migration is corrected by committing
a new, higher-numbered migration, never by editing an applied one (see ADR-7).
"""

import re
from pathlib import Path

from sqlalchemy import text

# migrations/ sits next to this file, inside the service.
MIGRATIONS_ROOT = Path(__file__).resolve().parent.parent / "migrations"

# A migration file is NNN_description.sql, e.g. 001_init.sql. The number orders them.
_FILENAME = re.compile(r"^(\d+)_.+\.sql$")


def _dialect_folder(engine):
    """Return the migrations subfolder matching the connected database."""
    name = engine.dialect.name  # "mssql" or "sqlite"
    folder = MIGRATIONS_ROOT / name
    if not folder.is_dir():
        raise RuntimeError(f"No migrations for dialect '{name}' at {folder}.")
    return folder


def _migration_files(folder):
    """Every migration file in the folder, sorted by its leading number."""
    files = []
    for path in folder.iterdir():
        match = _FILENAME.match(path.name)
        if match:
            files.append((int(match.group(1)), path))
    files.sort(key=lambda pair: pair[0])
    return [path for _, path in files]


def _split_batches(sql, dialect):
    """Split a migration script into the statements the driver can run one at a time.

    Both drivers execute a single statement per execute() call. SQL Server scripts use
    GO as the separator (pymssql rejects GO as a keyword); SQLite scripts use the
    ordinary ';'. Blank fragments and standalone comment lines are dropped.
    """
    separator_is_go = dialect == "mssql"
    batches, current = [], []

    if separator_is_go:
        for line in sql.splitlines():
            if line.strip().upper() == "GO":
                batches.append("\n".join(current))
                current = []
            else:
                current.append(line)
        batches.append("\n".join(current))
    else:
        # Strip full-line SQL comments so a trailing comment does not become an empty
        # statement, then split on ';'.
        lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
        batches = "\n".join(lines).split(";")

    return [batch.strip() for batch in batches if batch.strip()]


def run_migrations(engine):
    """Apply every pending migration in order. Safe to call on every startup."""
    folder = _dialect_folder(engine)

    with engine.begin() as connection:
        # The ledger of applied migrations. Created first, idempotently, so the very
        # first boot has somewhere to record what it ran.
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  filename VARCHAR(255) PRIMARY KEY,"
                "  applied_at DATETIME NOT NULL"
                ")"
            )
            if engine.dialect.name == "sqlite"
            else text(
                "IF OBJECT_ID(N'schema_migrations', N'U') IS NULL "
                "CREATE TABLE schema_migrations ("
                "  filename NVARCHAR(255) NOT NULL PRIMARY KEY,"
                "  applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()"
                ")"
            )
        )
        applied = {
            row[0]
            for row in connection.execute(text("SELECT filename FROM schema_migrations"))
        }

    for path in _migration_files(folder):
        if path.name in applied:
            continue
        # Each migration runs in its own transaction: it either fully applies and is
        # recorded, or it rolls back and the next boot retries it.
        with engine.begin() as connection:
            for batch in _split_batches(path.read_text(), engine.dialect.name):
                connection.execute(text(batch))
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (filename, applied_at) "
                    "VALUES (:filename, :applied_at)"
                ),
                {"filename": path.name, "applied_at": _now()},
            )
        print(f"migration applied: {path.name}", flush=True)


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)
