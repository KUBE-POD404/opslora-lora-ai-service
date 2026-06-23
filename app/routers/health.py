from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.providers.router import ProviderRouter
from app.schemas import ProviderHealth, ProvidersHealthResponse

router = APIRouter(tags=["health"])


def get_router(settings: Annotated[Settings, Depends(get_settings)]) -> ProviderRouter:
    return ProviderRouter(settings)


@router.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name, "environment": settings.environment}


@router.get("/health/providers")
async def providers_health(
    settings: Annotated[Settings, Depends(get_settings)],
    provider_router: Annotated[ProviderRouter, Depends(get_router)],
) -> ProvidersHealthResponse:
    statuses = await provider_router.health()
    return ProvidersHealthResponse(
        primary=settings.primary_ai_provider,
        providers=[ProviderHealth(**status.__dict__) for status in statuses],
    )
