# Deploying to Azure Container Apps

This is the owner's runbook for putting the demo on Azure Container Apps,
consumption plan, scaled to zero when idle, at `faa-demo.rogerkutyna.com`.

How it fits together: every push to `main` that passes the tests and the
image smoke test publishes the image to GitHub Container Registry (GHCR). The
deploy workflow then signs in to Azure with OpenID Connect (no stored
password), deploys `infra/main.bicep` into one resource group with the exact
image digest that was just published, and checks `/healthz`.

Nothing in the repository contains a subscription id, tenant id or email. They
live in repository secrets (the three Azure ids and the budget email) and a few
repository variables. The ids are identifiers, not credentials, but the
repository and its workflow logs are public and secrets are masked in logs,
while variables are not.

## 1. Prerequisites

- An Azure subscription where you can create resources, and the right to
  create app registrations in its Entra tenant.
- The Azure CLI (`az`), signed in with `az login`.
- The GitHub CLI (`gh`), signed in, or access to the repository settings page.
- The Cloudflare zone for `rogerkutyna.com`.

## 2. Run the bootstrap script

```bash
./scripts/bootstrap-azure.sh --subscription <subscription id or name>
```

Options: `--resource-group` (default `faa-demo-rg`), `--location` (default
`eastus`), `--repo` (default `rkutyna/fitness-analyst-demo`).

It registers the resource providers, creates the resource group, creates an
Entra app registration and service principal, adds a federated credential, and
gives that principal the Contributor role on the resource group only. It is
safe to run twice. It writes nothing to disk and creates no password.

The federated credential subject is
`repo:rkutyna/fitness-analyst-demo:environment:production`. The deploy job
declares `environment: production`, and GitHub then puts exactly that subject
in the token it presents to Azure. A job that does not use that environment
(a pull request, another branch, another job) cannot sign in as this principal.

## 3. Set the repository secrets and variables

The script ends by printing the exact commands. `gh secret set` stores
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID`;
`gh variable set` stores `AZURE_RESOURCE_GROUP` and `AZURE_DEPLOY_ENABLED`
(set to `true`). Run them yourself; the script does not.

Until the variable `AZURE_DEPLOY_ENABLED` is `true`, the deploy job is skipped
and CI stays green. The gate is a variable because a job-level condition cannot
read secrets. Set it last.

Optional, for a budget alert: store your address as the repository secret
`BUDGET_CONTACT_EMAIL` (`gh secret set BUDGET_CONTACT_EMAIL`). It is a secret
rather than a variable so that it is masked in the public workflow logs. With
it set, the next deploy also creates a monthly budget (default 5 in the
subscription's billing currency) with alerts at 80 percent of actual spend and
100 percent of forecast spend. A budget only sends email; it does not stop
anything. After that first deploy, pin the budget's start date so later
deploys do not try to move it:

```bash
gh variable set BUDGET_START_DATE --repo rkutyna/fitness-analyst-demo --body "<first day of the month the budget was created, yyyy-MM-01>"
```

## 4. Make the GHCR package public

The Container App pulls the image anonymously, so it holds no registry
credentials. That only works when the package is public.

The package appears after the first push to `main` completes the publish job.
Then: GitHub, your profile, Packages, `fitness-analyst-demo`, Package settings,
Danger Zone, Change visibility, Public. (If the package is not linked to the
repository, use "Connect repository" on the same page; the image carries the
source label that normally links it automatically.)

## 5. First deploy

The first push to `main` after step 3 deploys automatically. You can also run
it by hand: Actions, deploy, Run workflow. Leave the digest empty to deploy the
current `latest` image.

The job creates the Log Analytics workspace, the Container Apps environment and
the app, then waits for `https://<app fqdn>/healthz` to return 200. Allow a few
minutes the first time.

## 6. Verify

The deploy log prints the address, which looks like
`faa-demo.<random>.<region>.azurecontainerapps.io`. Open it. You should see the
demo, and `/readyz` should answer `{"status":"ready", ...}`. To see the address
again:

```bash
az containerapp show --resource-group faa-demo-rg --name faa-demo \
  --query properties.configuration.ingress.fqdn --output tsv
```

## 7. Custom domain with Cloudflare

Get the two values you need:

```bash
FQDN=$(az containerapp show -g faa-demo-rg -n faa-demo --query properties.configuration.ingress.fqdn -o tsv)
VERIFY=$(az containerapp env show -g faa-demo-rg -n faa-demo-env --query properties.customDomainConfiguration.customDomainVerificationId -o tsv)
echo "$FQDN"; echo "$VERIFY"
```

In Cloudflare DNS for `rogerkutyna.com`, add two records. Both must be
**DNS only** (grey cloud), not proxied, or Azure cannot validate the domain or
issue the certificate:

| Type | Name | Content |
|---|---|---|
| CNAME | `faa-demo` | the app address (`$FQDN`) |
| TXT | `asuid.faa-demo` | the verification id (`$VERIFY`) |

Wait until both resolve (`dig +short CNAME faa-demo.rogerkutyna.com`). Then add
the hostname and bind a free managed certificate:

```bash
az containerapp hostname add  -g faa-demo-rg -n faa-demo --hostname faa-demo.rogerkutyna.com
az containerapp hostname bind -g faa-demo-rg -n faa-demo --hostname faa-demo.rogerkutyna.com \
  --environment faa-demo-env --validation-method CNAME
```

Issuing the certificate takes a few minutes. Find the certificate's name:

```bash
az containerapp env certificate list -g faa-demo-rg -n faa-demo-env \
  --managed-certificates-only --query "[].name" -o tsv
```

**Do this step or the next deploy removes the domain.** A Bicep deployment
replaces the app's whole ingress configuration with what the template says. The
template therefore models the domain behind two optional parameters,
`customDomain` and `managedCertificateName`, and the deploy workflow passes
them from repository variables. Record the domain and the certificate name:

```bash
gh variable set CUSTOM_DOMAIN            --repo rkutyna/fitness-analyst-demo --body "faa-demo.rogerkutyna.com"
gh variable set MANAGED_CERTIFICATE_NAME --repo rkutyna/fitness-analyst-demo --body "<the certificate name from above>"
```

Why this approach and not "the redeploy preserves it": the template replaces the
ingress block, and nothing here relies on the service merging a custom domain back
in. Modelling it is explicit. The risk, plainly: the domain survives only while
those two variables are set and name a certificate that still exists. If you
clear them, deploy by hand with different parameters, or delete the
certificate, the next deploy drops the domain binding or fails. The managed
certificate is a child of the environment and is not touched by a redeploy.
Setting `customDomain` without a certificate name binds the hostname with
binding disabled, which is the state `hostname add` leaves it in.

If you run the Bicep by hand, pass the same two parameters.

Check `https://faa-demo.rogerkutyna.com/healthz`.

## Cost notes

Prices are not verified here and change; use the official pages:

- Azure Container Apps: <https://azure.microsoft.com/pricing/details/container-apps/>
- Azure Monitor and Log Analytics: <https://azure.microsoft.com/pricing/details/monitor/>
- Cost Management budgets: <https://learn.microsoft.com/azure/cost-management-billing/costs/tutorial-acm-create-budgets>

What drives cost here: the app is sized at 0.25 vCPU and 0.5 GiB, with
`minReplicas` 0 and `maxReplicas` 2, so with no traffic there are no running
replicas to bill for compute. Container Apps has a free monthly grant on the
consumption plan; check the pricing page for its current size. The Log
Analytics workspace bills for data ingested and for retention beyond its free
period; retention is set to 30 days. Console logs from the app are the only
thing ingested.

## Cold start with minimum replicas 0

When nobody has visited for a while the app scales to zero. The next request
starts a container, so it can take several seconds (image pull on a fresh node,
Python start, bundle validation) before the page appears. After that it is
fast until traffic stops again. The deploy workflow's health check retries for
about five minutes for this reason. If you would rather pay for no cold starts,
set the `minReplicas` parameter to 1.

## Rollback

Every deploy is pinned to an image digest. To go back, find the older digest
(GitHub, Packages, `fitness-analyst-demo`, the version list, or the publish job
log of the earlier run) and run Actions, deploy, Run workflow with that
`sha256:...` value in the digest box. The workflow redeploys the same template
with the old image and checks health again. A merge to `main` afterwards deploys
the new code again, so revert or fix on `main` as well.

## Teardown

Everything the template creates lives in one resource group, so deleting it
removes it all, including the logs and the budget:

```bash
az group delete --name faa-demo-rg --yes --no-wait
```

The Entra app registration made by the bootstrap script is separate. Delete it
with `az ad app delete --id <AZURE_CLIENT_ID>`, and remove the repository
secrets and variables. Remove the two DNS records in Cloudflare.
