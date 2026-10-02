#!/usr/bin/env bash
# One-time Azure setup for the deploy workflow. Safe to run again: every step
# checks whether it is already done. Writes nothing to disk and creates no
# secret: GitHub signs in with OpenID Connect, so there is no password to keep.
#
# Needs: the Azure CLI, a signed-in session (az login), and permission to
# create app registrations in the tenant and role assignments in the subscription.
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --subscription <id-or-name> [--resource-group faa-demo-rg]
          [--location eastus] [--repo rkutyna/fitness-analyst-demo]
USAGE
}

SUBSCRIPTION=""
RESOURCE_GROUP="faa-demo-rg"
LOCATION="eastus"
REPO="rkutyna/fitness-analyst-demo"
ENVIRONMENT="production"
APP_NAME="faa-demo-github-deploy"
CRED_NAME="github-${ENVIRONMENT}"

while [ $# -gt 0 ]; do
  case "$1" in
    --subscription)   SUBSCRIPTION="${2:?--subscription needs a value}"; shift 2 ;;
    --resource-group) RESOURCE_GROUP="${2:?--resource-group needs a value}"; shift 2 ;;
    --location)       LOCATION="${2:?--location needs a value}"; shift 2 ;;
    --repo)           REPO="${2:?--repo needs a value}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    *)                echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[ -n "$SUBSCRIPTION" ] || { echo "--subscription is required" >&2; usage >&2; exit 2; }

step() { printf '\n==> %s\n' "$*"; }

step "Selecting subscription"
az account set --subscription "$SUBSCRIPTION"
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
TENANT_ID=$(az account show --query tenantId --output tsv)

step "Registering resource providers (a no-op if already registered)"
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Consumption; do
  echo "registering $ns"
  az provider register --namespace "$ns" --wait
done

step "Creating resource group $RESOURCE_GROUP in $LOCATION (a no-op if it exists)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

step "Looking for app registration $APP_NAME"
CLIENT_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" --output tsv)
if [ -z "$CLIENT_ID" ]; then
  echo "creating it"
  CLIENT_ID=$(az ad app create --display-name "$APP_NAME" --query appId --output tsv)
else
  echo "found it"
fi

step "Looking for its service principal"
if ! az ad sp show --id "$CLIENT_ID" --output none 2>/dev/null; then
  echo "creating it"
  az ad sp create --id "$CLIENT_ID" --output none
else
  echo "found it"
fi
SP_OBJECT_ID=$(az ad sp show --id "$CLIENT_ID" --query id --output tsv)

# GitHub's OIDC token names the owner and the repository with their numeric
# ids as well (repo:owner@id/name@id:...), and Entra matches the subject
# exactly, so read both ids from the public API rather than guessing.
REPO_JSON=$(curl -fsSL "https://api.github.com/repos/${REPO}")
OWNER_ID=$(printf '%s' "$REPO_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["owner"]["id"])')
REPO_ID=$(printf '%s' "$REPO_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
SUBJECT="repo:${REPO%%/*}@${OWNER_ID}/${REPO#*/}@${REPO_ID}:environment:${ENVIRONMENT}"
step "Federated credential $CRED_NAME with subject $SUBJECT"
EXISTING=$(az ad app federated-credential list --id "$CLIENT_ID" \
  --query "[?name=='${CRED_NAME}'].subject | [0]" --output tsv)
if [ -z "$EXISTING" ]; then
  echo "creating it"
  az ad app federated-credential create --id "$CLIENT_ID" --parameters \
    "{\"name\":\"${CRED_NAME}\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"${SUBJECT}\",\"audiences\":[\"api://AzureADTokenExchange\"]}" \
    --output none
elif [ "$EXISTING" = "$SUBJECT" ]; then
  echo "already present"
else
  echo "updating it (the subject was ${EXISTING})"
  az ad app federated-credential update --id "$CLIENT_ID" --federated-credential-id "$CRED_NAME" --parameters \
    "{\"name\":\"${CRED_NAME}\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"${SUBJECT}\",\"audiences\":[\"api://AzureADTokenExchange\"]}" \
    --output none
fi

SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
step "Granting Contributor on the resource group only"
COUNT=$(az role assignment list --assignee "$SP_OBJECT_ID" --role Contributor --scope "$SCOPE" \
  --query "length(@)" --output tsv)
if [ "$COUNT" = 0 ]; then
  echo "creating the role assignment (a new service principal can take a minute to be visible; retrying)"
  for attempt in 1 2 3 4 5 6; do
    if az role assignment create --assignee-object-id "$SP_OBJECT_ID" \
         --assignee-principal-type ServicePrincipal --role Contributor --scope "$SCOPE" \
         --output none; then
      break
    fi
    [ "$attempt" != 6 ] || { echo "Role assignment kept failing." >&2; exit 1; }
    sleep 10
  done
else
  echo "already present"
fi

cat <<DONE

Done. Nothing was written to disk. Values for the repository:

  AZURE_CLIENT_ID        = ${CLIENT_ID}
  AZURE_TENANT_ID        = ${TENANT_ID}
  AZURE_SUBSCRIPTION_ID  = ${SUBSCRIPTION_ID}
  AZURE_RESOURCE_GROUP   = ${RESOURCE_GROUP}

Store the three ids as repository SECRETS (they are identifiers, not
credentials, but this repository and its logs are public and secrets are masked),
the rest as variables, with the GitHub CLI. Run them yourself:

  gh secret set   AZURE_CLIENT_ID       --repo ${REPO} --body "${CLIENT_ID}"
  gh secret set   AZURE_TENANT_ID       --repo ${REPO} --body "${TENANT_ID}"
  gh secret set   AZURE_SUBSCRIPTION_ID --repo ${REPO} --body "${SUBSCRIPTION_ID}"
  gh variable set AZURE_RESOURCE_GROUP  --repo ${REPO} --body "${RESOURCE_GROUP}"
  gh variable set AZURE_DEPLOY_ENABLED  --repo ${REPO} --body true

Set AZURE_DEPLOY_ENABLED last: it is what turns the deploy job on.

The deploy job signs in as environment "${ENVIRONMENT}", so create that
environment in the repository settings if it does not exist yet (GitHub also
creates it the first time a workflow names it).
DONE
