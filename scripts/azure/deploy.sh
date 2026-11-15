#!/usr/bin/env bash
# Run only by the CD job after all checks and SHA-tagged image publication succeed.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
[[ ${GITHUB_REF:-} == refs/heads/main && ${GITHUB_EVENT_NAME:-} == push ]] || {
  echo 'Deployment is only allowed on a push to main.' >&2; exit 1;
}
: "${HOUSEHOLD_DATABASE_URL:?missing GitHub secret}"
: "${FAIRNESS_DATABASE_URL:?missing GitHub secret}"
: "${AUTH_SECRET:?missing GitHub secret}"
export PREFIX LOCATION
export AZURE_CORE_ONLY_SHOW_ERRORS=true
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
ENVIRONMENT_ID=$(az containerapp env show -g "$RESOURCE_GROUP" -n "$ACA_ENV" --query id -o tsv)
UI_ORIGIN=$(az storage account show -g "$RESOURCE_GROUP" -n "$STORAGE_ACCOUNT" --query primaryEndpoints.web -o tsv)
UI_ORIGIN=${UI_ORIGIN%/}
export ENVIRONMENT_ID UI_ORIGIN
umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

for service in household fairness; do
  python3 scripts/azure/render_app.py "$service" "$work/app.json"
  if az containerapp show -g "$RESOURCE_GROUP" -n "$PREFIX-$service" -o none 2>/dev/null; then
    az containerapp update -g "$RESOURCE_GROUP" -n "$PREFIX-$service" --yaml "$work/app.json" -o none
  else
    az containerapp create -g "$RESOURCE_GROUP" -n "$PREFIX-$service" --yaml "$work/app.json" -o none
  fi
  fqdn=$(az containerapp show -g "$RESOURCE_GROUP" -n "$PREFIX-$service" --query properties.configuration.ingress.fqdn -o tsv)
  url="https://$fqdn"
  python3 scripts/azure/check_health.py "$url" "$GITHUB_SHA"
  if [[ $service == household ]]; then export HOUSEHOLD_URL="$url"; else export FAIRNESS_URL="$url"; fi
 done

# Stage the static build so local config.js stays local. JSON escaping is done by Python.
mkdir "$work/ui"
cp ui/* "$work/ui/"
python3 - "$work/ui/config.js" <<'PY'
import json, os, sys
config = {key: os.environ[key] for key in ('HOUSEHOLD_URL', 'FAIRNESS_URL')}
config['REQUEST_TIMEOUT_MS'] = 230000
with open(sys.argv[1], 'w') as stream:
    stream.write('window.HOUSEMATE_CONFIG = ' + json.dumps(config) + ';\n')
PY
az storage blob upload-batch --account-name "$STORAGE_ACCOUNT" --auth-mode login \
  --destination '$web' --source "$work/ui" --overwrite true --content-cache-control no-cache -o none
curl --fail --silent --show-error --max-time 30 "$UI_ORIGIN/config.js" > "$work/config.js"
cmp "$work/ui/config.js" "$work/config.js"
{
  echo '### HouseMate deployment'
  echo "Commit: \`$GITHUB_SHA\`"
  echo "UI: $UI_ORIGIN"
  echo "Household: $HOUSEHOLD_URL"
  echo "Fairness: $FAIRNESS_URL"
} >> "$GITHUB_STEP_SUMMARY"
