#!/usr/bin/env bash
# Store the OIDC IDs as Actions secrets and the deployment names as Actions variables.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
client_id=$(az identity show -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" --query clientId -o tsv)

printf '%s' "$client_id" | gh secret set AZURE_CLIENT_ID --repo "$GITHUB_REPO"
printf '%s' "$AZURE_TENANT_ID" | gh secret set AZURE_TENANT_ID --repo "$GITHUB_REPO"
printf '%s' "$AZURE_SUBSCRIPTION_ID" | gh secret set AZURE_SUBSCRIPTION_ID --repo "$GITHUB_REPO"

set_variable() {
  local name=$1 value=$2
  if gh api "repos/$GITHUB_REPO/actions/variables/$name" --silent 2>/dev/null; then
    gh api --method PATCH "repos/$GITHUB_REPO/actions/variables/$name" -f name="$name" -f value="$value" --silent
  else
    gh api --method POST "repos/$GITHUB_REPO/actions/variables" -f name="$name" -f value="$value" --silent
  fi
}
set_variable PREFIX "$PREFIX"
set_variable RESOURCE_GROUP "$RESOURCE_GROUP"
set_variable UI_STORAGE "$STORAGE_ACCOUNT"
echo 'GitHub Actions secrets and variables configured.'
