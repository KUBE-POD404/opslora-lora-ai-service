from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.schemas import (
    OperationsCustomer,
    OperationsInvoice,
    OperationsOrder,
    OperationsPayment,
    OperationsProduct,
    OperationsSnapshotRequest,
    OperationsStockBalance,
)
from app.services.live_context import (
    EMPTY_LIVE_SNAPSHOT_TEXT,
    LiveContextUnavailable,
    fetch_live_operations_snapshot,
    format_live_operations_context,
)


def test_format_live_operations_context_handles_missing_snapshot():
    context = format_live_operations_context(None)

    assert "No live Opslora service snapshot was fetched" in context
    assert "bearer token was not available" in context


def test_format_live_operations_context_lists_loaded_tenant_records():
    snapshot = OperationsSnapshotRequest(
        generated_at="2026-06-28T08:00:00Z",
        customers=[OperationsCustomer(id=7, name="Acme", status="ACTIVE")],
        orders=[
            OperationsOrder(
                id=42,
                customer_id=7,
                customer_name="Acme",
                total=99.5,
                status="CONFIRMED",
                created_at="2026-06-28T08:00:00Z",
            )
        ],
        invoices=[
            OperationsInvoice(
                id=5,
                invoice_number="INV-5",
                order_id=42,
                customer_name="Acme",
                total=99.5,
                status="UNPAID",
                due_date="2026-07-01",
                created_at="2026-06-28T08:00:00Z",
            )
        ],
        payments=[
            OperationsPayment(
                id=3,
                invoice_id=5,
                amount=25,
                currency="INR",
                payment_method="UPI",
                status="SUCCEEDED",
                paid_at="2026-06-28T08:10:00Z",
            )
        ],
        products=[OperationsProduct(id=2, name="Widget", sku="W-2", is_active=True)],
        stock_by_product={2: OperationsStockBalance(product_id=2, quantity_on_hand=3, low_stock_threshold=5)},
    )

    context = format_live_operations_context(snapshot)

    assert "Live tenant operations snapshot" in context
    assert "Order 42" in context
    assert "Invoice INV-5" in context
    assert "Payment 3" in context
    assert "Product 2" in context
    assert "on_hand=3" in context


@pytest.mark.asyncio
async def test_fetch_live_operations_snapshot_without_authorization_returns_none():
    snapshot = await fetch_live_operations_snapshot(Settings(), authorization=None)

    assert snapshot is None


@pytest.mark.asyncio
async def test_fetch_live_operations_snapshot_raises_on_forbidden_service(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "forbidden"})

    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)

    with pytest.raises(LiveContextUnavailable):
        await fetch_live_operations_snapshot(Settings(), authorization="Bearer token")


@pytest.mark.asyncio
async def test_fetch_live_operations_snapshot_loads_products_and_stock(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/customers/":
            return httpx.Response(200, json=[])
        if path == "/api/v1/orders/":
            return httpx.Response(200, json=[])
        if path == "/api/v1/invoices/":
            return httpx.Response(200, json=[])
        if path == "/api/v1/payments/":
            return httpx.Response(200, json=[])
        if path == "/api/v1/inventory/products":
            return httpx.Response(200, json=[{"id": 2, "name": "Widget", "sku": "W-2", "is_active": True}])
        if path == "/api/v1/inventory/stock/2":
            return httpx.Response(200, json={"quantity_on_hand": "4", "low_stock_threshold": "5"})
        return httpx.Response(404, json={"detail": path})

    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)

    snapshot = await fetch_live_operations_snapshot(Settings(), authorization="Bearer token")

    assert snapshot is not None
    assert snapshot.products[0].name == "Widget"
    assert snapshot.stock_by_product[2].quantity_on_hand == 4


def test_empty_live_snapshot_text_constant_is_used_for_empty_sections():
    snapshot = OperationsSnapshotRequest(generated_at="2026-06-28T08:00:00Z")

    context = format_live_operations_context(snapshot)

    assert context.count(EMPTY_LIVE_SNAPSHOT_TEXT) >= 5
