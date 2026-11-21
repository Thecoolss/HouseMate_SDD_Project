"""Create separate contained SQL users, verify isolation, then configure GitHub runtime secrets.

Passwords stay in the environment and GitHub stdin, never stdout. No application DDL.
Requires pymssql (already in each service's requirements).
"""
import os
import subprocess
import time
from urllib.parse import quote

import pymssql


def connect(user, password, database):
    for attempt in range(25):
        try:
            return pymssql.connect(
                server=os.environ['SQL_SERVER'] + '.database.windows.net',
                user=user, password=password, database=database,
                login_timeout=5, timeout=30, encryption='require', autocommit=True,
            )
        except pymssql.OperationalError:
            if attempt == 24:
                raise RuntimeError('SQL connection failed after bounded retries; check credentials/firewall/capacity.') from None
            time.sleep(5)


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def configure_user(cursor, user, password):
    cursor.execute('SELECT authentication_type_desc FROM sys.database_principals WHERE name=%s', (user,))
    existing = cursor.fetchone()
    if existing is None:
        cursor.execute(f'CREATE USER [{user}] WITH PASSWORD = {sql_literal(password)}, DEFAULT_SCHEMA = [dbo]')
    elif existing[0] != 'DATABASE':
        raise RuntimeError(f'{user} already exists and is not a contained user.')
    else:
        cursor.execute(f'ALTER USER [{user}] WITH DEFAULT_SCHEMA = [dbo]')

    for role in ('db_ddladmin', 'db_datareader', 'db_datawriter'):
        cursor.execute(f"""
            IF IS_ROLEMEMBER(N'{role}', N'{user}') <> 1
                ALTER ROLE [{role}] ADD MEMBER [{user}]
        """)
    cursor.execute(f"""
        IF IS_ROLEMEMBER(N'db_owner', N'{user}') = 1
            ALTER ROLE [db_owner] DROP MEMBER [{user}]
    """)


def verify_user(admin, admin_pw, login, password, database, other_database):
    with connect(login, password, database) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DB_NAME()')
        if cursor.fetchone()[0] != database:
            raise RuntimeError(f'{login} connected to the wrong database.')
        cursor.execute("""
            SELECT IS_ROLEMEMBER('db_ddladmin'), IS_ROLEMEMBER('db_datareader'),
                   IS_ROLEMEMBER('db_datawriter'), IS_ROLEMEMBER('db_owner')
        """)
        if cursor.fetchone() != (1, 1, 1, 0):
            raise RuntimeError(f'{login} does not have the expected database roles.')
    # Check the other database is awake via admin first, so a paused DB cannot be
    # mistaken for successful isolation.
    with connect(admin, admin_pw, other_database):
        pass
    try:
        unexpected = pymssql.connect(
            server=os.environ['SQL_SERVER'] + '.database.windows.net',
            user=login, password=password, database=other_database,
            login_timeout=10, encryption='require',
        )
    except pymssql.OperationalError as error:
        if not any(code in str(error) for code in ('4060', '916', '18456')):
            raise RuntimeError('Isolation probe failed for a reason other than access denied.') from None
    else:
        unexpected.close()
        raise RuntimeError('Database isolation failed')


def main():
    admin, admin_pw = os.environ['SQL_ADMIN'], os.environ['SQL_ADMIN_PASSWORD']
    prefix = os.environ['PREFIX']
    runtime_urls = {}
    for service in ('household', 'fairness'):
        login = service + '_app'
        password = os.environ[service.upper() + '_DB_PASSWORD']
        database = prefix + '-' + service + '-db'
        with connect(admin, admin_pw, database) as conn:
            configure_user(conn.cursor(), login, password)
        other = 'fairness' if service == 'household' else 'household'
        verify_user(admin, admin_pw, login, password, database, prefix + '-' + other + '-db')
        runtime_urls[service] = (
            f'mssql+pymssql://{login}:{quote(password, safe="")}@'
            f'{os.environ["SQL_SERVER"]}.database.windows.net:1433/{database}'
        )
        print(f'{service}: database roles and cross-database isolation verified')

    for service, url in runtime_urls.items():
        subprocess.run(['gh', 'secret', 'set', service.upper() + '_DATABASE_URL',
                        '--repo', os.environ['GITHUB_REPO']], input=url, text=True, check=True)
    subprocess.run(['gh', 'secret', 'set', 'AUTH_SECRET', '--repo', os.environ['GITHUB_REPO']],
                   input=os.environ['AUTH_SECRET'], text=True, check=True)


if __name__ == '__main__':
    main()
