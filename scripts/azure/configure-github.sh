#!/usr/bin/env bash
# Non-secret OIDC identifiers. REST API works even with older gh versions.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
client_id=$(az identity show -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" --query clientId -o tsv)
set_variable() {
  local name=$1 value=$2
  if gh api "repos/$GITHUB_REPO/actions/variables/$name" --silent 2>/dev/null; then
    gh api --method PATCH "repos/$GITHUB_REPO/actions/variables/$name" -f name="$name" -f value="$value" --silent
  else
    gh api --method POST "repos/$GITHUB_REPO/actions/variables" -f name="$name" -f value="$value" --silent
  fi
}
set_variable AZURE_CLIENT_ID "$client_id"
set_variable AZURE_TENANT_ID "$AZURE_TENANT_ID"
set_variable AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
echo 'GitHub OIDC variables configured.'
