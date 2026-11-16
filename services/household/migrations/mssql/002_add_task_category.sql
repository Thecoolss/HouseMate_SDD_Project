-- Adds a category to every task without losing existing rows.
-- WITH VALUES writes 'general' into the rows that already exist; without it SQL Server
-- would only use the default for future inserts. The CHECK constraint is added in a
-- second batch because SQL Server compiles a whole batch before running it, and the
-- column does not exist yet when the first batch is compiled.
ALTER TABLE task
ADD category NVARCHAR(40) NOT NULL
    CONSTRAINT df_task_category DEFAULT N'general' WITH VALUES;
GO

ALTER TABLE task
ADD CONSTRAINT ck_task_category
    CHECK (category IN (N'general', N'cleaning', N'cooking', N'shopping', N'maintenance'));
GO
