from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import OperationsSnapshotRequest
from app.services.operations_briefing import build_operations_briefing


def seeded_snapshot() -> dict:
    return {
        "generated_at": "2026-06-26T05:52:39.301Z",
        "customers": [
            {"id": 1, "name": "Acme Overdue Buyer 1782450820", "status": "ACTIVE"},
            {"id": 2, "name": "Bright Ready Buyer 1782450820", "status": "ACTIVE"},
        ],
        "invoices": [
            {
                "id": 1,
                "invoice_number": "LORA-000001-000001",
                "order_id": 1,
                "customer_name": "Acme Overdue Buyer 1782450820",
                "total": 3540.0,
                "status": "OVERDUE",
                "due_date": "2026-07-26",
                "created_at": "2026-06-26T05:13:49",
            }
        ],
        "orders": [
            {
                "id": 1,
                "customer_id": 1,
                "customer_name": "Acme Overdue Buyer 1782450820",
                "total": 3540.0,
                "status": "CONFIRMED",
                "created_at": "2026-06-26T05:13:49",
            },
            {
                "id": 2,
                "customer_id": 2,
                "customer_name": "Bright Ready Buyer 1782450820",
                "total": 2200.0,
                "status": "CONFIRMED",
                "created_at": "2026-06-26T05:13:50",
            },
        ],
        "payments": [],
        "products": [
            {"id": 3, "name": "Low Stock Motor 1782450820", "sku": "LORA-LOW-1782450820"}
        ],
        "stock_by_product": {"3": {"product_id": 3, "quantity_on_hand": 3, "low_stock_threshold": 10}},
    }


def test_build_operations_briefing_counts_seeded_facts():
    briefing = build_operations_briefing(OperationsSnapshotRequest(**seeded_snapshot()))

    assert briefing.summary.active_customers == 2
    assert briefing.summary.open_invoice_count == 1
    assert briefing.summary.overdue_invoice_count == 1
    assert briefing.summary.amount_due == 3540.0
    assert briefing.summary.orders_to_invoice_count == 1
    assert briefing.summary.low_stock_count == 1
    assert briefing.overdue_invoices[0].invoice_number == "LORA-000001-000001"
    assert briefing.orders_ready_to_invoice[0].id == 2
    assert briefing.low_stock_products[0].product.sku == "LORA-LOW-1782450820"
    assert "Active customers: 2." in briefing.prompt_context
    assert "Invoice LORA-000001-000001" in briefing.prompt_context


def test_operations_briefing_endpoint_returns_structured_summary():
    client = TestClient(app)
    response = client.post("/api/v1/ai/operations/briefing", json=seeded_snapshot())

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["active_customers"] == 2
    assert body["summary"]["amount_due"] == 3540.0
    assert body["orders_ready_to_invoice"][0]["customer_name"] == "Bright Ready Buyer 1782450820"
    assert body["low_stock_products"][0]["stock"]["quantity_on_hand"] == 3.0
    assert "Confirmed orders ready to invoice: 1" in body["prompt_context"]


def test_operations_briefing_empty_snapshot_is_authoritative():
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/operations/briefing",
        json={
            "generated_at": "2026-06-26T00:00:00Z",
            "invoices": [],
            "orders": [],
            "customers": [],
            "payments": [],
            "products": [],
            "stock_by_product": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["active_customers"] == 0
    assert body["summary"]["open_invoice_count"] == 0
    assert "None in the loaded snapshot" in body["prompt_context"]
    assert body["recommended_actions"] == [
        "No urgent operating exceptions found in the loaded snapshot; keep monitoring."
    ]
