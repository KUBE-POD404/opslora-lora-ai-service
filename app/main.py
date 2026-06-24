from __future__ import annotations

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers.health import router as health_router
from app.routers.v1.ai import router as ai_router

settings = get_settings()

app = FastAPI(title="Opslora Lora AI Service", version="2.0.1")
app.include_router(health_router)
app.include_router(ai_router, prefix=settings.api_prefix)
