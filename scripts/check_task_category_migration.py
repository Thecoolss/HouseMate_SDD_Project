"""Exercise the real 001 -> 002 upgrade on an EMPTY, disposable test database."""

import shutil
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def verify_upgrade(engine, migrations):
    original_root = migrations.MIGRATIONS_ROOT
    dialect = engine.dialect.name
    with tempfile.TemporaryDirectory() as directory:
        staged_root = Path(directory)
        staged = staged_root / dialect
        staged.mkdir()
        shutil.copy(original_root / dialect / "001_init.sql", staged)
        try:
            migrations.MIGRATIONS_ROOT = staged_root
            migrations.run_migrations(engine)
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO [user] (username, password_hash) VALUES ('migration-check', 'unused')"
                ))
                user_id = connection.execute(text("SELECT id FROM [user]")).scalar_one()
                for status in ("pending", "done"):
                    connection.execute(text(
                        "INSERT INTO task (title, description, difficulty, status, assigned_to, "
                        "created_by, due_date, created_at, completed_at) VALUES "
                        "(:title, 'Keep this description', 'hard', :status, :owner, :owner, "
                        "'2026-11-20T12:00:00', '2026-11-16T12:00:00', :completed)"
                    ), {"title": "Migration " + status, "status": status, "owner": user_id,
                        "completed": "2026-11-16T13:00:00" if status == "done" else None})
                before = connection.execute(text("SELECT * FROM task ORDER BY id")).mappings().all()

            shutil.copy(original_root / dialect / "002_add_task_category.sql", staged)
            migrations.run_migrations(engine)
            migrations.run_migrations(engine)
            with engine.begin() as connection:
                after = connection.execute(text("SELECT * FROM task ORDER BY id")).mappings().all()
                assert len(after) == len(before) == 2
                for old, new in zip(before, after):
                    assert {key: new[key] for key in old} == dict(old)
                    assert new["category"] == "general"
                ledger = connection.execute(text(
                    "SELECT filename FROM schema_migrations ORDER BY filename"
                )).scalars().all()
                assert ledger == ["001_init.sql", "002_add_task_category.sql"]
                # An older application inserting without category still works.
                connection.execute(text(
                    "INSERT INTO task (title, difficulty, status, created_by, created_at) "
                    "VALUES ('After upgrade', 'easy', 'pending', :owner, '2026-11-16T14:00:00')"
                ), {"owner": user_id})
                assert connection.execute(text(
                    "SELECT category FROM task WHERE title = 'After upgrade'"
                )).scalar_one() == "general"
                # Every category the API accepts must also pass the database constraint.
                for category in ("cleaning", "cooking", "shopping", "maintenance"):
                    connection.execute(text(
                        "INSERT INTO task (title, category, difficulty, status, created_by, "
                        "created_at) VALUES (:title, :category, 'easy', 'pending', :owner, "
                        "'2026-11-16T15:00:00')"
                    ), {"title": "Allowed " + category, "category": category, "owner": user_id})

            # The CHECK constraint rejects a value outside the list. Own transaction, so the
            # failed insert cannot affect the rows checked above.
            try:
                with engine.begin() as connection:
                    connection.execute(text(
                        "INSERT INTO task (title, category, difficulty, status, created_by, "
                        "created_at) VALUES ('Bad', 'gardening', 'easy', 'pending', :owner, "
                        "'2026-11-16T16:00:00')"
                    ), {"owner": user_id})
            except DBAPIError as error:
                assert "ck_task_category" in str(error), error
            else:
                raise AssertionError("ck_task_category accepted an invalid category")

            with engine.begin() as connection:
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM task WHERE title = 'Bad'"
                )).scalar_one() == 0
                # Leave this disposable database empty for the remaining smoke checks.
                connection.execute(text("DELETE FROM task"))
                connection.execute(text("DELETE FROM [user]"))
        finally:
            migrations.MIGRATIONS_ROOT = original_root
    print(
        "Task category upgrade: existing rows preserved, default works, constraint "
        "enforced, applied once."
    )


if __name__ == "__main__":
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    from app import migrations

    url = make_url(os.environ["DATABASE_URL"])
    if url.host != "sqlserver" or url.database != "household":
        raise SystemExit("Only the disposable Compose household database is supported.")
    engine = create_engine(url)
    try:
        verify_upgrade(engine, migrations)
    finally:
        engine.dispose()
