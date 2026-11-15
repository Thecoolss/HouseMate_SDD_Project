#!/usr/bin/env bash
# One-time SQL logins/users only. Leaves application schema creation to first CD startup.
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/azure/config.sh
set -a
source .azure-local/secrets.env
export SQL_SERVER SQL_ADMIN PREFIX GITHUB_REPO
set +a
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
# Grant this machine access only while the setup runs; preserve any other firewall rules.
ip=$(curl --fail --silent --show-error --max-time 15 https://api.ipify.org)
python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$ip"
rule="housemate-setup-$$"
cleanup() { az sql server firewall-rule delete -g "$RESOURCE_GROUP" -s "$SQL_SERVER" -n "$rule" -o none; }
trap cleanup EXIT
az sql server firewall-rule create -g "$RESOURCE_GROUP" -s "$SQL_SERVER" -n "$rule" \
  --start-ip-address "$ip" --end-ip-address "$ip" -o none
"${PYTHON:-python3}" scripts/azure/init_databases.py
