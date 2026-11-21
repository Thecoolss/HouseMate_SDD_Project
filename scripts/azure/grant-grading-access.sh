#!/usr/bin/env bash
# Grant the two graders Reader access to this assignment's resource group.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
scope=$(az group show --name "$RESOURCE_GROUP" --query id -o tsv)

for professor in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee "$professor" --role Reader --scope "$scope" \
    --query '{role:roleDefinitionName,scope:scope}' -o json
  echo "Reader access configured for $professor."
done
