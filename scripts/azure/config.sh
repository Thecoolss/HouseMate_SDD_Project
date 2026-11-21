#!/usr/bin/env bash
# Non-secret configuration, shared by setup and CD. Only HouseMate names belong here.
AZURE_SUBSCRIPTION_ID=1ffa64df-6785-4731-83b0-629fe825fda4
AZURE_TENANT_ID=4a39c578-6df0-42b9-a7e0-e9eac6d91816
PREFIX=sdroubi-ieu2024
RESOURCE_GROUP=rg-sdroubi-ieu2024
# France Central from the slides is forbidden by this subscription's region policy.
LOCATION=germanywestcentral
STORAGE_ACCOUNT=sdroubiieu2024ui
SQL_SERVER=${PREFIX}-sql
SQL_ADMIN=housemate_admin
ACA_ENV=${PREFIX}-env
LOG_WORKSPACE=${PREFIX}-logs
DEPLOY_IDENTITY=${PREFIX}-github
GITHUB_REPO=Thecoolss/HouseMate_SDD_Project
# GitHub's immutable OIDC subject includes the owner and repository IDs.
# Must exactly match the subject claim printed by azure/login for main.
GITHUB_OIDC_IMMUTABLE_SUBJECT=repo:Thecoolss@148555406/HouseMate_SDD_Project@1380508437:ref:refs/heads/main
GITHUB_OIDC_SUBJECT="repo:${GITHUB_REPO}:ref:refs/heads/main"
