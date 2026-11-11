-- Creates one database and one login per service. Run by the db-init compose service.
--
-- Idempotent: every statement checks first, so running it on every `docker compose up`
-- is safe and changes nothing the second time. Re-running also re-applies the passwords,
-- so changing a password in .env takes effect on the next `up`.
--
-- $(HOUSEHOLD_DB_PASSWORD) and $(FAIRNESS_DB_PASSWORD) are sqlcmd scripting variables.
-- sqlcmd fills them from the db-init container's environment, so no password is written
-- in this file.
--
-- Each login gets a user in its own database only. With no user in the other database
-- (and guest disabled there by default), a service cannot read the other's data.

-- household ------------------------------------------------------------------------------
IF DB_ID(N'household') IS NULL
    CREATE DATABASE household;
GO

IF SUSER_ID(N'household_user') IS NULL
    CREATE LOGIN household_user
        WITH PASSWORD = N'$(HOUSEHOLD_DB_PASSWORD)', DEFAULT_DATABASE = household;
ELSE
    ALTER LOGIN household_user WITH PASSWORD = N'$(HOUSEHOLD_DB_PASSWORD)';
GO

USE household;
GO

IF DATABASE_PRINCIPAL_ID(N'household_user') IS NULL
    CREATE USER household_user FOR LOGIN household_user;
-- db_owner inside its own database only: the service creates and alters its own tables.
IF IS_ROLEMEMBER(N'db_owner', N'household_user') = 0
    ALTER ROLE db_owner ADD MEMBER household_user;
GO

-- fairness -------------------------------------------------------------------------------
USE master;
GO

IF DB_ID(N'fairness') IS NULL
    CREATE DATABASE fairness;
GO

IF SUSER_ID(N'fairness_user') IS NULL
    CREATE LOGIN fairness_user
        WITH PASSWORD = N'$(FAIRNESS_DB_PASSWORD)', DEFAULT_DATABASE = fairness;
ELSE
    ALTER LOGIN fairness_user WITH PASSWORD = N'$(FAIRNESS_DB_PASSWORD)';
GO

USE fairness;
GO

IF DATABASE_PRINCIPAL_ID(N'fairness_user') IS NULL
    CREATE USER fairness_user FOR LOGIN fairness_user;
IF IS_ROLEMEMBER(N'db_owner', N'fairness_user') = 0
    ALTER ROLE db_owner ADD MEMBER fairness_user;
GO
