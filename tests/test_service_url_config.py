from app.core.config import Settings


def test_default_internal_service_urls_use_cluster_dns():
    settings = Settings()

    assert settings.customer_service_url.endswith("://customer-service:3000")
    assert settings.order_service_url.endswith("://order-service:3000")
    assert settings.invoice_service_url.endswith("://invoice-service:3000")
    assert settings.payment_service_url.endswith("://payment-service:3000")
    assert settings.inventory_service_url.endswith("://inventory-service:3000")
