#!/usr/bin/env bash
# One-time, rerunnable foundation setup. Does not deploy service images or run migrations.
# Run from the repository: bash scripts/azure/setup.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
export AZURE_CORE_ONLY_SHOW_ERRORS=true
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
[[ $(az account show --query tenantId -o tsv) == "$AZURE_TENANT_ID" ]]

# Generate credentials once. Keep the file outside Git, with owner-only permissions.
mkdir -p .azure-local
chmod 700 .azure-local
python3 - <<'PY'
import os, secrets
from pathlib import Path
p = Path('.azure-local/secrets.env')
if not p.exists():
    with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        for key in ('SQL_ADMIN_PASSWORD', 'HOUSEHOLD_DB_PASSWORD', 'FAIRNESS_DB_PASSWORD', 'AUTH_SECRET'):
            f.write(f'{key}=Hm{secrets.token_hex(24)}9!\n')
PY
set -a
source .azure-local/secrets.env
set +a

for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace "$provider" --wait
 done
az group create -n "$RESOURCE_GROUP" -l "$LOCATION" --tags project=HouseMate -o none
az monitor log-analytics workspace create -g "$RESOURCE_GROUP" -n "$LOG_WORKSPACE" \
  -l "$LOCATION" --retention-time 30 --sku PerGB2018 -o none
workspace_id=$(az monitor log-analytics workspace show -g "$RESOURCE_GROUP" -n "$LOG_WORKSPACE" --query customerId -o tsv)
workspace_key=$(az monitor log-analytics workspace get-shared-keys -g "$RESOURCE_GROUP" -n "$LOG_WORKSPACE" --query primarySharedKey -o tsv)
az containerapp env create -g "$RESOURCE_GROUP" -n "$ACA_ENV" -l "$LOCATION" \
  --enable-workload-profiles true --logs-workspace-id "$workspace_id" --logs-workspace-key "$workspace_key" -o none
unset workspace_key

az storage account create -g "$RESOURCE_GROUP" -n "$STORAGE_ACCOUNT" -l "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --https-only true \
  --allow-blob-public-access false -o none
# Static website access is separate from blob-container public access. Use an ephemeral
# account key for this initial setup; CD uses its managed identity and data-plane RBAC.
AZURE_STORAGE_KEY=$(az storage account keys list -g "$RESOURCE_GROUP" -n "$STORAGE_ACCOUNT" --query '[0].value' -o tsv)
export AZURE_STORAGE_KEY
az storage blob service-properties update --account-name "$STORAGE_ACCOUNT" \
  --static-website --index-document index.html --404-document index.html -o none
unset AZURE_STORAGE_KEY

# Do not reset the admin password when rerunning setup against an existing server.
if ! az sql server show -g "$RESOURCE_GROUP" -n "$SQL_SERVER" -o none 2>/dev/null; then
  az sql server create -g "$RESOURCE_GROUP" -n "$SQL_SERVER" -l "$LOCATION" \
    -u "$SQL_ADMIN" -p "$SQL_ADMIN_PASSWORD" --minimal-tls-version 1.2 -o none
fi
az sql server firewall-rule create -g "$RESOURCE_GROUP" -s "$SQL_SERVER" \
  -n AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none
for service in household fairness; do
  az sql db create -g "$RESOURCE_GROUP" -s "$SQL_SERVER" -n "$PREFIX-$service-db" \
    --edition GeneralPurpose --family Gen5 --capacity 1 --compute-model Serverless \
    --min-capacity 0.5 --auto-pause-delay 15 --max-size 2GB \
    --backup-storage-redundancy Local --zone-redundant false -o none
 done

az identity create -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" -l "$LOCATION" -o none
principal_id=$(az identity show -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" --query principalId -o tsv)
scope="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$scope" -o none
az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
  --role 'Storage Blob Data Contributor' --scope "$scope/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT" -o none
az identity federated-credential create -g "$RESOURCE_GROUP" --identity-name "$DEPLOY_IDENTITY" \
  -n github-main --issuer https://token.actions.githubusercontent.com \
  --subject "repo:$GITHUB_REPO:ref:refs/heads/main" --audiences api://AzureADTokenExchange -o none

bash scripts/azure/configure-github.sh

printf 'Foundation ready. Initialise service logins with bash scripts/azure/init-databases.sh\n'
az storage account show -g "$RESOURCE_GROUP" -n "$STORAGE_ACCOUNT" --query primaryEndpoints.web -o tsv
