from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

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
from app.services.operations_briefing import build_operations_briefing

EMPTY_LIVE_SNAPSHOT_TEXT = "None in the live tenant snapshot."


class LiveContextUnavailable(RuntimeError):
    pass


async def fetch_live_operations_snapshot(
    settings: Settings,
    *,
    authorization: str | None,
) -> OperationsSnapshotRequest | None:
    """Fetch a live tenant-scoped operations snapshot through existing service APIs.

    Lora does not invent its own tenant filtering. It forwards the caller's bearer
    token to the same service APIs the frontend uses, so each service applies its
    existing JWT permission and organization checks before returning data.
    """
    if not authorization:
        return None

    headers = {"Authorization": authorization}
    timeout = settings.operations_context_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        customers = await _get_list(client, settings.customer_service_url, "/api/v1/customers/?limit=100")
        orders = await _get_list(client, settings.order_service_url, "/api/v1/orders/?limit=100")
        invoices = await _get_list(client, settings.invoice_service_url, "/api/v1/invoices/?limit=100")
        payments = await _get_list(client, settings.payment_service_url, "/api/v1/payments/")
        products = await _get_list(client, settings.inventory_service_url, "/api/v1/inventory/products?limit=100")

        stock_by_product: dict[int, OperationsStockBalance] = {}
        for product in products[: settings.operations_context_stock_limit]:
            product_id = _int_or_none(product.get("id"))
            if product_id is None:
                continue
            try:
                stock = await _get_object(
                    client,
                    settings.inventory_service_url,
                    f"/api/v1/inventory/stock/{product_id}",
                )
            except LiveContextUnavailable:
                continue
            stock_by_product[product_id] = OperationsStockBalance(
                product_id=product_id,
                quantity_on_hand=_float_or_zero(stock.get("quantity_on_hand")),
                low_stock_threshold=_float_or_zero(stock.get("low_stock_threshold")),
            )

    return OperationsSnapshotRequest(
        generated_at=datetime.now(UTC).isoformat(),
        customers=[_customer(item) for item in customers],
        orders=[_order(item) for item in orders],
        invoices=[_invoice(item) for item in invoices],
        payments=[_payment(item) for item in payments],
        products=[_product(item) for item in products],
        stock_by_product=stock_by_product,
    )


def format_live_operations_context(snapshot: OperationsSnapshotRequest | None) -> str:
    if snapshot is None:
        return (
            "No live Opslora service snapshot was fetched. A bearer token was not "
            "available, so answer only from retrieved tenant knowledge context."
        )

    briefing = build_operations_briefing(snapshot)
    order_lines = _format_orders(snapshot.orders)
    invoice_lines = _format_invoices(snapshot.invoices)
    customer_lines = _format_customers(snapshot.customers)
    payment_lines = _format_payments(snapshot.payments)
    product_lines = _format_products(snapshot.products, snapshot.stock_by_product)

    return "\n".join(
        [
            "Live tenant operations snapshot from Opslora services.",
            "This data was fetched using the caller's authorization token; treat it as tenant-scoped.",
            briefing.prompt_context,
            "All loaded orders:",
            order_lines,
            "All loaded invoices:",
            invoice_lines,
            "All loaded customers:",
            customer_lines,
            "All loaded payments:",
            payment_lines,
            "All loaded products and stock:",
            product_lines,
        ]
    )


async def _get_list(client: httpx.AsyncClient, base_url: str, path: str) -> list[dict[str, Any]]:
    data = await _get_object(client, base_url, path)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("items", "data", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


async def _get_object(client: httpx.AsyncClient, base_url: str, path: str) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    response = await client.get(url)
    if response.status_code in {401, 403}:
        raise LiveContextUnavailable(f"Unauthorized while fetching {path}")
    response.raise_for_status()
    return response.json()


def _customer(item: dict[str, Any]) -> OperationsCustomer:
    return OperationsCustomer(
        id=_int_or_zero(item.get("id")),
        name=_string_or_none(item.get("name") or item.get("display_name")),
        status=_string_or_none(item.get("status")),
    )


def _order(item: dict[str, Any]) -> OperationsOrder:
    return OperationsOrder(
        id=_int_or_zero(item.get("id")),
        customer_id=_int_or_zero(item.get("customer_id")),
        customer_name=_string_or_none(item.get("customer_name")),
        total=_float_or_zero(item.get("total") or item.get("grand_total")),
        status=str(item.get("status") or "UNKNOWN"),
        created_at=_string_or_none(item.get("created_at")),
    )


def _invoice(item: dict[str, Any]) -> OperationsInvoice:
    return OperationsInvoice(
        id=_int_or_zero(item.get("id")),
        invoice_number=_string_or_none(item.get("invoice_number")),
        order_id=_int_or_zero(item.get("order_id")),
        customer_name=_string_or_none(item.get("customer_name")),
        total=_float_or_zero(item.get("total") or item.get("grand_total")),
        status=str(item.get("status") or "UNKNOWN"),
        due_date=_string_or_none(item.get("due_date")),
        created_at=_string_or_none(item.get("created_at")),
    )


def _payment(item: dict[str, Any]) -> OperationsPayment:
    return OperationsPayment(
        id=_int_or_zero(item.get("id")),
        invoice_id=_int_or_zero(item.get("invoice_id")),
        amount=_float_or_zero(item.get("amount")),
        currency=_string_or_none(item.get("currency")),
        payment_method=_string_or_none(item.get("payment_method")),
        status=str(item.get("status") or "UNKNOWN"),
        paid_at=_string_or_none(item.get("paid_at")),
    )


def _product(item: dict[str, Any]) -> OperationsProduct:
    return OperationsProduct(
        id=_int_or_zero(item.get("id")),
        name=str(item.get("name") or "Unnamed product"),
        sku=str(item.get("sku") or ""),
        is_active=bool(item.get("is_active", True)),
    )


def _format_orders(items: list[OperationsOrder]) -> str:
    if not items:
        return EMPTY_LIVE_SNAPSHOT_TEXT
    return "\n".join(
        f"- Order {item.id}: customer={item.customer_name or item.customer_id}; "
        f"status={item.status}; total={item.total:.2f}; created_at={item.created_at or 'unknown'}"
        for item in items[:25]
    )


def _format_invoices(items: list[OperationsInvoice]) -> str:
    if not items:
        return EMPTY_LIVE_SNAPSHOT_TEXT
    return "\n".join(
        f"- Invoice {item.invoice_number or item.id}: order={item.order_id}; "
        f"customer={item.customer_name or 'unknown'}; status={item.status}; total={item.total:.2f}; "
        f"due={item.due_date or 'unknown'}"
        for item in items[:25]
    )


def _format_customers(items: list[OperationsCustomer]) -> str:
    if not items:
        return EMPTY_LIVE_SNAPSHOT_TEXT
    return "\n".join(
        f"- Customer {item.id}: {item.name or 'unknown'}; status={item.status or 'unknown'}"
        for item in items[:25]
    )


def _format_payments(items: list[OperationsPayment]) -> str:
    if not items:
        return EMPTY_LIVE_SNAPSHOT_TEXT
    return "\n".join(
        f"- Payment {item.id}: invoice={item.invoice_id}; status={item.status}; "
        f"amount={item.amount:.2f} {item.currency or ''}; paid_at={item.paid_at or 'unknown'}"
        for item in items[:25]
    )


def _format_products(
    items: list[OperationsProduct], stock_by_product: dict[int, OperationsStockBalance]
) -> str:
    if not items:
        return EMPTY_LIVE_SNAPSHOT_TEXT
    lines = []
    for item in items[:25]:
        stock = stock_by_product.get(item.id)
        stock_text = (
            f"on_hand={stock.quantity_on_hand}; threshold={stock.low_stock_threshold}"
            if stock
            else "stock=unknown"
        )
        lines.append(f"- Product {item.id}: {item.name}; sku={item.sku}; active={item.is_active}; {stock_text}")
    return "\n".join(lines)


def _int_or_zero(value: Any) -> int:
    parsed = _int_or_none(value)
    return parsed if parsed is not None else 0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
