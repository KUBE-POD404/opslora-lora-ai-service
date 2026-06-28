from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_id: str
    chunk_id: str
    chunk_index: int
    source_uri: str | None = None
    snippet: str


class ChatRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    use_fallback: bool = True
    preferred_provider: str | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str | None = None
    response: str
    fallback_used: bool = False
    conversation_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)


class KnowledgeIngestRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    user_id: str | None = None
    source_type: str = Field(default="text", min_length=1, max_length=64)
    source_uri: str | None = Field(default=None, max_length=1024)
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)
    visibility_scope: str = Field(default="organization", min_length=1, max_length=64)
    retention_policy: str | None = Field(default=None, max_length=128)


class KnowledgeIngestResponse(BaseModel):
    source_id: str
    chunks_created: int
    status: str


class ProviderHealth(BaseModel):
    name: str
    configured: bool
    available: bool
    detail: str | None = None


class ProvidersHealthResponse(BaseModel):
    primary: str
    providers: list[ProviderHealth]


class OperationsInvoice(BaseModel):
    id: int
    invoice_number: str | None = None
    order_id: int
    customer_name: str | None = None
    total: float = 0
    status: str
    due_date: str | None = None
    created_at: str | None = None


class OperationsOrder(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    total: float = 0
    status: str
    created_at: str | None = None


class OperationsCustomer(BaseModel):
    id: int
    name: str | None = None
    status: str | None = None


class OperationsPayment(BaseModel):
    id: int
    invoice_id: int
    amount: float = 0
    currency: str | None = None
    payment_method: str | None = None
    status: str
    paid_at: str | None = None


class OperationsProduct(BaseModel):
    id: int
    name: str
    sku: str
    is_active: bool = True


class OperationsStockBalance(BaseModel):
    product_id: int
    quantity_on_hand: float = 0
    low_stock_threshold: float = 0


class OperationsSnapshotRequest(BaseModel):
    generated_at: str
    invoices: list[OperationsInvoice] = Field(default_factory=list)
    orders: list[OperationsOrder] = Field(default_factory=list)
    customers: list[OperationsCustomer] = Field(default_factory=list)
    payments: list[OperationsPayment] = Field(default_factory=list)
    products: list[OperationsProduct] = Field(default_factory=list)
    stock_by_product: dict[int, OperationsStockBalance] = Field(default_factory=dict)


class OperationsSummaryMetrics(BaseModel):
    active_customers: int
    open_invoice_count: int
    overdue_invoice_count: int
    amount_due: float
    collected: float
    orders_to_invoice_count: int
    draft_order_count: int
    low_stock_count: int


class OperationsLowStockItem(BaseModel):
    product: OperationsProduct
    stock: OperationsStockBalance


class OperationsBriefingResponse(BaseModel):
    summary: OperationsSummaryMetrics
    overdue_invoices: list[OperationsInvoice]
    orders_ready_to_invoice: list[OperationsOrder]
    low_stock_products: list[OperationsLowStockItem]
    prompt_context: str
    recommended_actions: list[str]
