# Opslora lora-ai CI/CD setup requirements

This file lists the external GitHub/Azure/Sonar/Snyk setup required before the new pipelines can run without interruption. No secrets are stored here.

## GitHub environments

Create or confirm these environments on `opslora-lora-ai-service`:

- `azure-test`
- `azure-prod`

Each environment should have:

- `AZURE_CLIENT_ID` secret: OIDC app/client id with access to the target subscription and AcrPush on the target ACR.
- `AZURE_TENANT_ID` secret.
- `AZURE_SUBSCRIPTION_ID` secret.
- `HELM_REPO_TOKEN` secret: token/app credential that can write to `KUBE-POD404/opslora-helm-charts` branch `azure/agic-application-gateway`.
- `SNYK_TOKEN` secret if Snyk is the chosen dependency scanner.
- `SONAR_TOKEN` secret for SonarCloud.
- `AZURE_ACR_NAME` variable: ACR resource name, not login server. The workflow resolves login server with `az acr show`.
- Optional `SONAR_ORGANIZATION` variable. Default used by workflow: `kube-pod404`.
- Optional `SONAR_PROJECT_KEY` variable. Default used by workflow: `KUBE-POD404_opslora-lora-ai-service`.

## Azure role assignments

The GitHub OIDC identity needs:

- AcrPush on the ACR for build/push.
- Reader on the ACR/resource group if needed for `az acr show`.

AKS kubelet/managed identity needs:

- AcrPull on the same ACR.

## SonarCloud

Create the SonarCloud project before making the PR gate required:

- organization: `kube-pod404` unless changed
- project key: `KUBE-POD404_opslora-lora-ai-service` unless changed

## Branch protection

On `main`, require the aggregate check:

- `PR required gates`

This aggregate waits on:

- tests and lint
- Alembic migration check
- CodeQL SAST
- SonarCloud quality gate
- Snyk dependency scan
- container build and Trivy scan

## CD approach

Normal CD is GitOps:

- app repo merge to `main` builds/scans/pushes to ACR
- app repo workflow updates Helm values in `opslora-helm-charts`
- ArgoCD syncs AKS from Helm repo

Do not use direct `helm upgrade` from the service repo for normal application CD.
