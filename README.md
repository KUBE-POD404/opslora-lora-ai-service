# Opslora Lora AI Service

Tenant-aware AI microservice for Opslora.

Primary provider: on-prem Ollama/Hermes over private VPN. Local smoke tests use `smollm2:135m` by default because it is small enough for bootstrap validation.
Fallback provider: Azure AI Foundry when enabled and configured.

Local run:

```bash
uv venv
uv pip install -r requirements.txt -r requirements-dev.txt
ollama pull smollm2:135m
ENV_FILE=.env.example .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Local container smoke deploy, assuming Ollama is already listening on the host at `127.0.0.1:11434`:

```bash
docker build -t opslora/lora-ai-service:local .
docker run -d --name opslora-lora-ai-local --network host \
  -e ENVIRONMENT=development \
  -e HERMES_BASE_URL=http://127.0.0.1:11434 \
  -e HERMES_MODEL=smollm2:135m \
  opslora/lora-ai-service:local
curl -fsS http://127.0.0.1:8080/health
```

## Health endpoints

- `GET /health` - lightweight pod health for Kubernetes readiness/liveness probes.
- `GET /health/providers` - provider-router health for Ollama/Hermes and Azure AI Foundry.
- `GET /api/v1/ai/health` - versioned API health endpoint for callers.
- `GET /api/v1/ai/providers` - versioned provider health response.

## Application logic

The service now has the first usable application layer for tenant-aware AI:

- `POST /api/v1/ai/knowledge/sources` stores organization-scoped knowledge sources and chunks them for retrieval.
- `POST /api/v1/ai/chat` creates or continues a conversation, retrieves matching tenant knowledge chunks, injects them into the model prompt, saves user/assistant messages, and returns citations.
- `GET /api/v1/ai/providers` reports Ollama/Hermes and Azure AI Foundry provider health.
- Conversation, message, knowledge, audit, tool-call, and usage tables are created by the baseline Alembic migration.

Current retrieval is a deterministic keyword retriever over stored chunks. This is deliberate bootstrap logic so the API is useful before a vector database is available. The next RAG increment is to add embeddings plus a vector-store adapter behind the existing `VECTOR_URL` / `VECTOR_API_KEY` configuration.

## Chat API contract

Internal AKS callers should use the Kubernetes service DNS name:

```text
http://lora-ai-service.opslora-app-ns.svc.cluster.local:8080
```

The stable chat endpoint is:

```http
POST /api/v1/ai/chat
Content-Type: application/json

{
  "organization_id": "org-or-tenant-id",
  "user_id": "calling-user-id",
  "message": "Ask Lora a business question",
  "conversation_id": "optional-conversation-id",
  "use_fallback": true
}
```

Response:

```json
{
  "provider": "ollama",
  "model": "qwen2.5:0.5b",
  "response": "assistant text",
  "fallback_used": false
}
```

If all configured AI providers are unavailable, the endpoint returns HTTP 503 with `detail` describing provider unavailability.

## Runtime environment contract

No provider secrets should be committed. Use normal env vars or `*_FILE` mounted secret paths. In AKS, the lora-ai Helm chart syncs Azure Key Vault objects into the `lora-ai-secret` Kubernetes Secret via the Secrets Store CSI driver and injects them with `envFrom`.

| Variable | Secret? | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | no | Runtime environment name (`development`, `test`, `production`). |
| `SERVICE_NAME` | no | Service identity in health responses; default `opslora-lora-ai-service`. |
| `API_PREFIX` | no | Versioned API prefix; default `/api/v1`. |
| `DATABASE_URL` / `DATABASE_URL_FILE` | yes | SQLAlchemy database URL for AI metadata/conversation storage. |
| `DATABASE_POOL_SIZE` | no | DB pool size; default `5`. |
| `DATABASE_MAX_OVERFLOW` | no | DB pool overflow; default `10`. |
| `DATABASE_POOL_RECYCLE_SECONDS` | no | DB connection recycle seconds; default `1800`. |
| `DATABASE_POOL_PRE_PING` | no | Enable SQLAlchemy pre-ping; default `true`. |
| `PRIMARY_AI_PROVIDER` | no | Primary provider router key; default `ollama`. |
| `ENABLE_AZURE_FOUNDRY_FALLBACK` | no | Allows Azure Foundry fallback when primary fails. |
| `HERMES_BASE_URL` | yes | Private Ollama/Hermes-compatible base URL reachable from AKS over VPN/private routing. |
| `HERMES_API_KEY` / `HERMES_API_KEY_FILE` | yes | Optional bearer token for the primary provider. |
| `HERMES_MODEL` | no | Primary model/deployment name. |
| `HERMES_TIMEOUT_SECONDS` | no | Primary provider timeout. |
| `AZURE_AI_FOUNDRY_ENDPOINT` | yes | Azure AI Foundry endpoint used only when fallback is enabled. |
| `AZURE_AI_FOUNDRY_API_KEY` / `AZURE_AI_FOUNDRY_API_KEY_FILE` | yes | Azure Foundry API key. |
| `AZURE_AI_FOUNDRY_DEPLOYMENT` | no | Azure Foundry deployment/model name. |
| `AZURE_AI_FOUNDRY_TIMEOUT_SECONDS` | no | Azure Foundry provider timeout. |
| `VECTOR_URL` | yes | Vector store endpoint for future retrieval features. |
| `VECTOR_API_KEY` / `VECTOR_API_KEY_FILE` | yes | Optional vector store credential. |

## AKS/Helm notes

- Chart path: `opslora-helm/apps/lora-ai` in the `opslora-helm-charts` repository.
- Azure app-of-apps manifests: `env/azure-test/apps/lora-ai.yaml` and `env/azure-prod/apps/lora-ai.yaml`.
- Cluster-internal service name: `lora-ai-service` on port `8080` in namespace `opslora-app-ns`.
- Probe path: `/health` for readiness and liveness.
- Image repository: `ghcr.io/kube-pod404/opslora-lora-ai-service`; environment overlays keep `azure-test-placeholder` / `azure-prod-placeholder` tags so CI/release automation can replace them with build-specific tags matching the existing chart pattern.