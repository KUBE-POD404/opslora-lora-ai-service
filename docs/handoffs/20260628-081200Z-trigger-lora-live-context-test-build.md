# Lora live context test build trigger

Timestamp: 20260628-081200Z

This no-op documentation change exists to trigger the approved Lora AI service test image pipeline after PR #9 merged without the `build` label.

The service code being deployed is already on `main` via PR #9:

- Live tenant-scoped Opslora service context in `/api/v1/ai/chat`
- Caller Authorization forwarding to customer/order/invoice/payment/inventory services
- Conversation organization isolation regression coverage
- Provider selection support
- Coverage and Sonar fixes

Deploy path should remain GitHub CI -> ACR -> Helm test values -> ArgoCD.
