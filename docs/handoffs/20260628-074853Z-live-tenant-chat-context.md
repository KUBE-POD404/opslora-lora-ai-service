# Lora live tenant chat context

Timestamp: 20260628-074853Z
Repo: opslora-lora-ai-service
Branch: fix/live-tenant-chat-context

## Why

Lora could answer `zero orders / zero invoices` when users asked for tenant data because `/api/v1/ai/chat` only used stored knowledge retrieval unless the frontend explicitly generated and ingested an operations snapshot. Direct questions such as `list all orders` needed live service data by default.

## What changed

- Added `app/services/live_context.py` to fetch live Opslora tenant data during chat.
- Lora chat now forwards the caller's `Authorization` header to existing service APIs:
  - customer-service: `/api/v1/customers/?limit=100`
  - order-service: `/api/v1/orders/?limit=100`
  - invoice-service: `/api/v1/invoices/?limit=100`
  - payment-service: `/api/v1/payments/`
  - inventory-service: `/api/v1/inventory/products?limit=100`
  - inventory-service stock balances: `/api/v1/inventory/stock/{product_id}`
- Tenant isolation relies on each existing service's JWT permissions and organization checks, rather than Lora inventing its own cross-tenant filter.
- Chat prompt now includes:
  - organization_id
  - user_id
  - conversation_id
  - retrieved tenant knowledge context
  - live tenant operations context
- Prompt explicitly tells Lora never to answer with data from another organization or another conversation.
- Existing `_get_or_create_conversation` org check remains in place; regression test verifies cross-organization conversation IDs return 404.
- Added optional `preferred_provider` on chat requests and provider-router support so frontend provider selection is functional.
- Added service URL/settings config for live context.
- Added `lora_ai_local.db` to `.gitignore` to avoid committing local SQLite runtime data.

## Files changed

- `.gitignore`
- `app/core/config.py`
- `app/providers/router.py`
- `app/routers/v1/ai.py`
- `app/schemas.py`
- `app/services/live_context.py`
- `tests/test_knowledge_chat.py`
- `tests/test_live_tenant_chat.py`

## Validation

From `/tmp/opslora-lora-live-tenant-tools`:

```text
uv run pytest tests/test_live_tenant_chat.py tests/test_knowledge_chat.py tests/test_operations_briefing.py -q
# 8 passed, 1 warning in 0.39s
```

New regression coverage:

- Chat forwards bearer token to service APIs.
- Live context contains real order/customer facts in the model prompt.
- Conversation IDs cannot be reused across organizations.

## Runtime notes

Default service URLs match Kubernetes service DNS names in namespace `opslora-app-ns`:

- `http://customer-service:3000`
- `http://order-service:3000`
- `http://invoice-service:3000`
- `http://payment-service:3000`
- `http://inventory-service:3000`

These can be overridden with `CUSTOMER_SERVICE_URL`, `ORDER_SERVICE_URL`, `INVOICE_SERVICE_URL`, `PAYMENT_SERVICE_URL`, and `INVENTORY_SERVICE_URL`.
