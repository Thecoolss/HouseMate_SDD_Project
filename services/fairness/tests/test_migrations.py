"""The migration runner: applies each file once, in order, and records it."""

import pytest
from sqlalchemy import create_engine, text

from app import migrations


@pytest.fixture()
def engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'm.db'}")


def _applied(engine):
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT filename FROM schema_migrations ORDER BY filename"))
        return [row[0] for row in rows]


def test_first_run_applies_every_migration_and_records_it(engine):
    migrations.run_migrations(engine)

    assert _applied(engine) == ["001_init.sql"]
    with engine.connect() as connection:
        connection.execute(text("SELECT * FROM contribution_score")).fetchall()


def test_second_run_applies_nothing(engine, capsys):
    migrations.run_migrations(engine)
    capsys.readouterr()

    migrations.run_migrations(engine)

    assert "migration applied" not in capsys.readouterr().out
    assert _applied(engine) == ["001_init.sql"]


def test_a_new_migration_runs_once_and_keeps_existing_rows(engine, tmp_path, monkeypatch):
    folder = tmp_path / "migrations"
    (folder / "sqlite").mkdir(parents=True)
    (folder / "sqlite" / "001_init.sql").write_text("CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT);")
    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", folder)
    migrations.run_migrations(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO t (a) VALUES ('keep me')"))

    (folder / "sqlite" / "002_add_b.sql").write_text(
        "ALTER TABLE t ADD COLUMN b TEXT DEFAULT 'x';\nUPDATE t SET b = upper(a);"
    )
    migrations.run_migrations(engine)
    migrations.run_migrations(engine)

    assert _applied(engine) == ["001_init.sql", "002_add_b.sql"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT a, b FROM t")).all() == [("keep me", "KEEP ME")]


def test_a_failing_migration_rolls_back_its_data_and_is_not_recorded(engine, tmp_path, monkeypatch):
    # Only data changes are asserted: SQLite's driver commits DDL implicitly, so it cannot
    # show a CREATE TABLE rolling back (SQL Server DDL is transactional).
    folder = tmp_path / "migrations"
    (folder / "sqlite").mkdir(parents=True)
    (folder / "sqlite" / "001_init.sql").write_text("CREATE TABLE t (v TEXT);")
    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", folder)
    migrations.run_migrations(engine)

    (folder / "sqlite" / "002_bad.sql").write_text(
        "INSERT INTO t VALUES ('half-applied');\nINSERT INTO missing_table VALUES (1);"
    )
    with pytest.raises(Exception):
        migrations.run_migrations(engine)

    assert _applied(engine) == ["001_init.sql"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM t")).scalar() == 0


def test_migrations_apply_in_numeric_order(engine, tmp_path, monkeypatch):
    folder = tmp_path / "migrations"
    (folder / "sqlite").mkdir(parents=True)
    (folder / "sqlite" / "010_c.sql").write_text("INSERT INTO t VALUES ('c');")
    (folder / "sqlite" / "002_b.sql").write_text("INSERT INTO t VALUES ('b');")
    (folder / "sqlite" / "001_a.sql").write_text("CREATE TABLE t (v TEXT);")
    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", folder)

    migrations.run_migrations(engine)

    with engine.connect() as connection:
        assert [row[0] for row in connection.execute(text("SELECT v FROM t ORDER BY rowid"))] == ["b", "c"]


def test_mssql_scripts_are_split_on_go():
    script = "CREATE TABLE a (x INT);\nGO\nCREATE TABLE b (y INT);\nGO\n"

    assert migrations._split_batches(script, "mssql") == [
        "CREATE TABLE a (x INT);",
        "CREATE TABLE b (y INT);",
    ]


def test_sqlite_scripts_are_split_on_semicolons_and_ignore_comments():
    script = "-- a comment\nCREATE TABLE a (x INT);\n-- another\nCREATE TABLE b (y INT);\n"

    assert migrations._split_batches(script, "sqlite") == [
        "CREATE TABLE a (x INT)",
        "CREATE TABLE b (y INT)",
    ]
