-- Adds a category to every task without losing existing rows. SQLite fills existing rows
-- with the default. SQLite cannot add a table constraint to an existing table, so the
-- CHECK is declared on the new column instead.
ALTER TABLE task ADD COLUMN category TEXT NOT NULL DEFAULT 'general'
    CONSTRAINT ck_task_category
    CHECK (category IN ('general', 'cleaning', 'cooking', 'shopping', 'maintenance'));
