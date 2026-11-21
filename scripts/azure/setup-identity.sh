#!/usr/bin/env bash
# Provision the deployment identity and the two main-branch federation subjects.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

az identity create -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" -l "$LOCATION" -o none
principal_id=$(az identity show -g "$RESOURCE_GROUP" -n "$DEPLOY_IDENTITY" --query principalId -o tsv)
scope="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$scope" -o none
az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
  --role 'Storage Blob Data Contributor' --scope "$scope/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT" -o none
az identity federated-credential create -g "$RESOURCE_GROUP" --identity-name "$DEPLOY_IDENTITY" \
  -n github-main --issuer https://token.actions.githubusercontent.com \
  --subject "$GITHUB_OIDC_SUBJECT" --audiences api://AzureADTokenExchange -o none
az identity federated-credential create -g "$RESOURCE_GROUP" --identity-name "$DEPLOY_IDENTITY" \
  -n github-main-immutable --issuer https://token.actions.githubusercontent.com \
  --subject "$GITHUB_OIDC_IMMUTABLE_SUBJECT" --audiences api://AzureADTokenExchange -o none
