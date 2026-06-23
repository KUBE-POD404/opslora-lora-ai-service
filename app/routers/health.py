from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.providers.router import ProviderRouter
from app.schemas import ProviderHealth, ProvidersHealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name, "environment": settings.environment}


@router.get("/health/providers", response_model=ProvidersHealthResponse)
async def provider_health(settings: Settings = Depends(get_settings)) -> ProvidersHealthResponse:
    statuses = await ProviderRouter(settings).health()
    return ProvidersHealthResponse(
        primary=settings.primary_ai_provider,
        providers=[ProviderHealth(**asdict(status)) for status in statuses],
    )
