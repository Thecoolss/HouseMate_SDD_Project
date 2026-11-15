"""Create separate SQL logins, verify isolation, then configure GitHub runtime secrets.

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


def main():
    admin, admin_pw = os.environ['SQL_ADMIN'], os.environ['SQL_ADMIN_PASSWORD']
    prefix = os.environ['PREFIX']
    for service in ('household', 'fairness'):
        login = service + '_user'
        password = os.environ[service.upper() + '_DB_PASSWORD']
        database = prefix + '-' + service + '-db'
        with connect(admin, admin_pw, 'master') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM sys.sql_logins WHERE name=%s', (login,))
            if not cursor.fetchone():
                cursor.execute(f'CREATE LOGIN [{login}] WITH PASSWORD = {sql_literal(password)}')
        with connect(admin, admin_pw, database) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM sys.database_principals WHERE name=%s', (login,))
            if not cursor.fetchone():
                cursor.execute(f'CREATE USER [{login}] FOR LOGIN [{login}]')
            cursor.execute(f"ALTER ROLE db_owner ADD MEMBER [{login}]")
        with connect(login, password, database) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DB_NAME()')
            assert cursor.fetchone()[0] == database
        other = 'fairness' if service == 'household' else 'household'
        # Check the other database is awake via admin first, so a paused DB cannot be
        # mistaken for successful isolation.
        with connect(admin, admin_pw, prefix + '-' + other + '-db'):
            pass
        try:
            unexpected = pymssql.connect(
                server=os.environ['SQL_SERVER'] + '.database.windows.net',
                user=login, password=password, database=prefix + '-' + other + '-db',
                login_timeout=10, encryption='require',
            )
        except pymssql.OperationalError as error:
            if not any(code in str(error) for code in ('4060', '916', '18456')):
                raise RuntimeError('Isolation probe failed for a reason other than access denied.') from None
        else:
            unexpected.close()
            raise RuntimeError('Database isolation failed')
        url = (f'mssql+pymssql://{login}:{quote(password, safe="")}@'
               f'{os.environ["SQL_SERVER"]}.database.windows.net:1433/{database}')
        subprocess.run(['gh', 'secret', 'set', service.upper() + '_DATABASE_URL',
                        '--repo', os.environ['GITHUB_REPO']], input=url, text=True, check=True)
        print(f'{service}: own database access verified; other database denied; GitHub secret configured')
    subprocess.run(['gh', 'secret', 'set', 'AUTH_SECRET', '--repo', os.environ['GITHUB_REPO']],
                   input=os.environ['AUTH_SECRET'], text=True, check=True)


if __name__ == '__main__':
    main()
