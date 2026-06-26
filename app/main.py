from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.core.config import get_settings
from app.database import initialize_sqlite_schema_if_needed
from app.routers.health import router as health_router
from app.routers.v1.ai import router as ai_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_sqlite_schema_if_needed()
    yield


app = FastAPI(title="Opslora Lora AI Service", version="2.0.1", lifespan=lifespan)
app.include_router(health_router)
app.include_router(ai_router, prefix=settings.api_prefix)
