from __future__ import annotations

import uuid

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.database import Base, engine
from app.main import app
from app.providers.base import CompletionResult
from app.routers.v1.ai import get_router


class CapturingProviderRouter:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def health(self):
        return []

    async def complete(self, prompt: str, *, allow_fallback: bool = True, preferred_provider: str | None = None):
        self.prompts.append(prompt)
        return CompletionResult(
            provider="fake",
            model="unit-test",
            text="Order 501 is CONFIRMED for Acme Buyer with total 1200.00.",
        ), False


def test_chat_injects_live_tenant_operations_context(monkeypatch):
    Base.metadata.create_all(bind=engine)
    provider = CapturingProviderRouter()
    app.dependency_overrides[get_router] = lambda: provider
    app.dependency_overrides[get_settings] = lambda: Settings(
        customer_service_url="http://customer-service",
        order_service_url="http://order-service",
        invoice_service_url="http://invoice-service",
        payment_service_url="http://payment-service",
        inventory_service_url="http://inventory-service",
    )

    requested: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((str(request.url), request.headers.get("authorization")))
        path = request.url.path
        if request.url.host == "customer-service" and path == "/api/v1/customers/":
            return httpx.Response(200, json=[{"id": 10, "name": "Acme Buyer", "status": "ACTIVE"}])
        if request.url.host == "order-service" and path == "/api/v1/orders/":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 501,
                        "customer_id": 10,
                        "customer_name": "Acme Buyer",
                        "total": 1200,
                        "status": "CONFIRMED",
                        "created_at": "2026-06-28T07:00:00Z",
                    }
                ],
            )
        if request.url.host == "invoice-service" and path == "/api/v1/invoices/":
            return httpx.Response(200, json=[])
        if request.url.host == "payment-service" and path == "/api/v1/payments/":
            return httpx.Response(200, json=[])
        if request.url.host == "inventory-service" and path == "/api/v1/inventory/products":
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": str(request.url)})

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda *args, **kwargs: httpx.MockTransport(handler))
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)

    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/chat",
        headers={"Authorization": "Bearer tenant-token"},
        json={
            "organization_id": f"org-{uuid.uuid4()}",
            "user_id": "user-1",
            "message": "Can you list all orders?",
            "use_fallback": False,
        },
    )

    assert response.status_code == 200
    assert requested
    assert {auth for _, auth in requested} == {"Bearer tenant-token"}
    prompt = provider.prompts[-1]
    assert "Live tenant operations snapshot from Opslora services" in prompt
    assert "Order 501" in prompt
    assert "Acme Buyer" in prompt
    assert "Confirmed orders ready to invoice: 1" in prompt

    app.dependency_overrides.clear()


def test_chat_rejects_conversation_id_from_another_organization():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_router] = lambda: CapturingProviderRouter()
    client = TestClient(app)

    first = client.post(
        "/api/v1/ai/chat",
        json={
            "organization_id": f"org-{uuid.uuid4()}",
            "user_id": "user-1",
            "message": "Start isolated conversation",
            "use_fallback": False,
        },
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/ai/chat",
        json={
            "organization_id": f"org-{uuid.uuid4()}",
            "user_id": "user-2",
            "conversation_id": conversation_id,
            "message": "Try to reuse another tenant conversation",
            "use_fallback": False,
        },
    )

    assert second.status_code == 404
    assert second.json()["detail"] == "Conversation not found for organization"

    app.dependency_overrides.clear()
