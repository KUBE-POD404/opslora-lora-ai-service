from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from app.schemas import (
    OperationsBriefingResponse,
    OperationsInvoice,
    OperationsLowStockItem,
    OperationsOrder,
    OperationsProduct,
    OperationsSnapshotRequest,
    OperationsStockBalance,
    OperationsSummaryMetrics,
)

OPEN_INVOICE_STATUSES = {"UNPAID", "PARTIALLY_PAID", "OVERDUE"}
SUCCESSFUL_PAYMENT_STATUSES = {"SUCCEEDED", "PARTIALLY_REFUNDED", "REFUNDED"}


def money(value: float | int | str | None) -> str:
    return f"Rs {float(value or 0):.2f}"


def short_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%d %b %Y")


def _is_overdue(invoice: OperationsInvoice) -> bool:
    if invoice.status == "OVERDUE":
        return True
    if not invoice.due_date:
        return False
    try:
        due_date = datetime.fromisoformat(invoice.due_date.replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return due_date < datetime.utcnow().date()


T = TypeVar("T")


def _top(items: list[T], limit: int = 6) -> list[T]:
    return items[:limit]


def build_operations_briefing(snapshot: OperationsSnapshotRequest) -> OperationsBriefingResponse:
    collectible_invoices = [
        invoice for invoice in snapshot.invoices if invoice.status in OPEN_INVOICE_STATUSES
    ]
    overdue_invoices = [invoice for invoice in collectible_invoices if _is_overdue(invoice)]
    order_ids_with_invoices = {invoice.order_id for invoice in snapshot.invoices}
    orders_ready_to_invoice = [
        order
        for order in snapshot.orders
        if order.status == "CONFIRMED" and order.id not in order_ids_with_invoices
    ]
    draft_orders = [order for order in snapshot.orders if order.status == "CREATED"]
    successful_payments = [
        payment for payment in snapshot.payments if payment.status in SUCCESSFUL_PAYMENT_STATUSES
    ]
    low_stock_products = _low_stock_items(snapshot.products, snapshot.stock_by_product)

    summary = OperationsSummaryMetrics(
        active_customers=len(
            [customer for customer in snapshot.customers if customer.status != "INACTIVE"]
        ),
        open_invoice_count=len(collectible_invoices),
        overdue_invoice_count=len(overdue_invoices),
        amount_due=sum(float(invoice.total or 0) for invoice in collectible_invoices),
        collected=sum(float(payment.amount or 0) for payment in successful_payments),
        orders_to_invoice_count=len(orders_ready_to_invoice),
        draft_order_count=len(draft_orders),
        low_stock_count=len(low_stock_products),
    )

    prompt_context = _format_prompt_context(
        snapshot=snapshot,
        summary=summary,
        overdue_or_open=overdue_invoices or collectible_invoices,
        orders_ready_to_invoice=orders_ready_to_invoice,
        low_stock_products=low_stock_products,
    )
    return OperationsBriefingResponse(
        summary=summary,
        overdue_invoices=overdue_invoices,
        orders_ready_to_invoice=orders_ready_to_invoice,
        low_stock_products=low_stock_products,
        prompt_context=prompt_context,
        recommended_actions=_recommended_actions(summary),
    )


def _low_stock_items(
    products: list[OperationsProduct], stock_by_product: dict[int, OperationsStockBalance]
) -> list[OperationsLowStockItem]:
    items: list[OperationsLowStockItem] = []
    for product in products:
        stock = stock_by_product.get(product.id)
        if stock and float(stock.quantity_on_hand) <= float(stock.low_stock_threshold):
            items.append(OperationsLowStockItem(product=product, stock=stock))
    return items


def _format_prompt_context(
    *,
    snapshot: OperationsSnapshotRequest,
    summary: OperationsSummaryMetrics,
    overdue_or_open: list[OperationsInvoice],
    orders_ready_to_invoice: list[OperationsOrder],
    low_stock_products: list[OperationsLowStockItem],
) -> str:
    invoice_lines = [
        "- Invoice "
        f"{invoice.invoice_number or invoice.id} for {invoice.customer_name or 'unknown customer'}: "
        f"{money(invoice.total)}, status {invoice.status}, due {short_date(invoice.due_date)}."
        for invoice in _top(overdue_or_open)
    ]
    order_lines = [
        "- Order "
        f"{order.id} for {order.customer_name or f'customer {order.customer_id}'}: "
        f"{money(order.total)}, created {short_date(order.created_at)}."
        for order in _top(orders_ready_to_invoice)
    ]
    stock_lines = [
        "- "
        f"{item.product.name} ({item.product.sku}) on hand "
        f"{item.stock.quantity_on_hand:.2f}, threshold {item.stock.low_stock_threshold:.2f}."
        for item in _top(low_stock_products)
    ]
    return "\n".join(
        [
            f"Opslora live operations snapshot generated at {snapshot.generated_at}.",
            "This snapshot is authoritative for the loaded organization window. Do not "
            "invent invoices, orders, customers, products, amounts, or due dates that are "
            "not listed here.",
            "If a count is zero, say there are no matching items in the loaded snapshot "
            "and recommend verification/monitoring actions instead of naming fake records.",
            f"Active customers: {summary.active_customers}.",
            "Open invoices: "
            f"{summary.open_invoice_count}; overdue invoices: {summary.overdue_invoice_count}; "
            f"amount due: {money(summary.amount_due)}.",
            f"Collected payments in loaded window: {money(summary.collected)}.",
            "Confirmed orders ready to invoice: "
            f"{summary.orders_to_invoice_count}; draft orders: {summary.draft_order_count}.",
            f"Low-stock products: {summary.low_stock_count}.",
            "Top overdue/open invoices:",
            *(invoice_lines or ["- None in the loaded snapshot."]),
            "Confirmed orders ready to invoice:",
            *(order_lines or ["- None in the loaded snapshot."]),
            "Low-stock products:",
            *(stock_lines or ["- None in the loaded snapshot."]),
        ]
    )


def _recommended_actions(summary: OperationsSummaryMetrics) -> list[str]:
    actions: list[str] = []
    if summary.overdue_invoice_count:
        actions.append("Prioritize overdue invoice collection follow-up.")
    if summary.orders_to_invoice_count:
        actions.append("Create invoices for confirmed orders that are ready to bill.")
    if summary.low_stock_count:
        actions.append("Review replenishment for low-stock products before fulfilment is blocked.")
    if not actions:
        actions.append("No urgent operating exceptions found in the loaded snapshot; keep monitoring.")
    return actions
