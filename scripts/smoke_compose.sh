#!/usr/bin/env bash
# Brings up the whole compose stack (SQL Server, db-init, both services, UI) and checks it
# end to end: migrations ran once, the cross-seam flow works on SQL Server, and each side
# behaves as designed when the other is stopped. Used by CI; also runnable locally.
#
# Needs a .env (copy .env.example) and free ports 5000, 5001 and 8080, so stop your own
# stack first. Exits non-zero on the first failed check.
set -euo pipefail
cd "$(dirname "$0")/.."

H=http://localhost:5000
F=http://localhost:5001
JSON='Content-Type: application/json'

fail() {
  echo "FAIL: $*"
  docker compose ps -a
  docker compose logs --no-color --tail 40
  exit 1
}
check() { # check <description> <expected> <actual>
  if [ "$2" == "$3" ]; then echo "ok   $1"; else fail "$1: expected '$2', got '$3'"; fi
}
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
json() { python3 -c "import sys, json; print(json.load(sys.stdin)$1)"; }
sql() { # sql <database> <query>  (prints the first value)
  docker compose exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa \
    -P "$MSSQL_SA_PASSWORD" -C -h -1 -W -d "$1" -Q "SET NOCOUNT ON; $2" | head -1 | tr -d '[:space:]'
}

set -a; source .env; set +a

# A separate compose project gets its own containers and its own SQL Server volume, so the
# checks always start from an empty database and never touch your normal `docker compose up`
# data. Everything in this project, volume included, is removed on exit.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-housemate-smoke}"
trap 'docker compose down -v >/dev/null 2>&1' EXIT
docker compose down -v >/dev/null 2>&1 || true

echo "== start the stack (project: $COMPOSE_PROJECT_NAME) =="
docker compose up --build -d --wait || fail "stack did not become healthy"

echo "== migrations =="
check "household applied 001_init" 1 "$(docker compose logs household | grep -c 'migration applied: 001_init.sql')"
check "fairness applied 001_init" 1 "$(docker compose logs fairness | grep -c 'migration applied: 001_init.sql')"
check "household schema_migrations rows" 1 "$(sql household 'SELECT COUNT(*) FROM schema_migrations')"
check "fairness schema_migrations rows" 1 "$(sql fairness 'SELECT COUNT(*) FROM schema_migrations')"

echo "== health =="
check "household /health" 200 "$(status $H/health)"
check "fairness /health" 200 "$(status $F/health)"

echo "== cross-seam flow on SQL Server =="
TOKEN=$(curl -sf -X POST $H/register -H "$JSON" -d '{"username":"smoke","password":"pw"}' | json "['token']")
AUTH="Authorization: Bearer $TOKEN"
TASK=$(curl -sf -X POST $H/tasks -H "$AUTH" -H "$JSON" -d '{"title":"Mop","difficulty":"hard"}' | json "['id']")
curl -sf -o /dev/null -X POST $H/tasks/$TASK/claim -H "$AUTH"
curl -sf -o /dev/null -X POST $H/tasks/$TASK/complete -H "$AUTH"
RECALC=$(curl -s -w '\n%{http_code}' -X POST $F/fairness/recalculate -H "$AUTH")
check "recalculate status" 201 "$(echo "$RECALC" | tail -1)"
check "smoke user's share" 100.0 "$(echo "$RECALC" | head -1 | json "['scores'][0]['contribution_score']")"
check "fairness page names from household" smoke "$(curl -s $F/fairness -H "$AUTH" | json "['rows'][0]['username']")"

echo "== restart: data kept, nothing re-applied =="
docker compose restart household fairness >/dev/null
docker compose up -d --wait >/dev/null || fail "stack did not recover after restart"
check "household schema_migrations rows" 1 "$(sql household 'SELECT COUNT(*) FROM schema_migrations')"
check "task survived the restart" 1 "$(sql household 'SELECT COUNT(*) FROM task')"
check "snapshot survived the restart" 1 "$(sql fairness 'SELECT COUNT(*) FROM contribution_score')"

echo "== household stopped =="
docker compose stop household >/dev/null
check "fairness /health" 200 "$(status $F/health)"
check "fairness page still answers" 200 "$(status $F/fairness -H "$AUTH")"
check "household_available" False "$(curl -s $F/fairness -H "$AUTH" | json "['household_available']")"
check "recalculate fails cleanly" 503 "$(status --max-time 10 -X POST $F/fairness/recalculate -H "$AUTH")"
docker compose start household >/dev/null

echo "== fairness stopped =="
docker compose stop fairness >/dev/null
docker compose up -d --wait household >/dev/null || fail "household did not come back"
check "household /tasks still answers" 200 "$(status $H/tasks -H "$AUTH")"
docker compose start fairness >/dev/null

echo "== UI served =="
check "ui index.html" 200 "$(status http://localhost:8080/index.html)"

echo "all smoke checks passed"
