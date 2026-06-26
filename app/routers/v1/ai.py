from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.models.ai import AIConversation, AIMessage, AIUsageEvent
from app.providers.router import ProviderRouter
from app.schemas import (
    ChatRequest,
    ChatResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    OperationsBriefingResponse,
    OperationsSnapshotRequest,
    ProviderHealth,
    ProvidersHealthResponse,
)
from app.services.knowledge import citations_for, format_context, ingest_knowledge, retrieve_context
from app.services.operations_briefing import build_operations_briefing

router = APIRouter(prefix="/ai", tags=["ai"])


def get_router(settings: Annotated[Settings, Depends(get_settings)]) -> ProviderRouter:
    return ProviderRouter(settings)


@router.get("/health")
async def ai_health() -> dict[str, str]:
    return {"status": "ok", "service": "lora-ai"}


@router.get("/providers")
async def provider_health(
    settings: Annotated[Settings, Depends(get_settings)],
    provider_router: Annotated[ProviderRouter, Depends(get_router)],
) -> ProvidersHealthResponse:
    statuses = await provider_router.health()
    return ProvidersHealthResponse(
        primary=settings.primary_ai_provider,
        providers=[ProviderHealth(**asdict(status)) for status in statuses],
    )


@router.post("/knowledge/sources")
def ingest_source(
    request: KnowledgeIngestRequest,
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeIngestResponse:
    source, chunk_count = ingest_knowledge(db, request)
    return KnowledgeIngestResponse(source_id=source.id, chunks_created=chunk_count, status=source.status)


@router.post("/operations/briefing")
def operations_briefing(request: OperationsSnapshotRequest) -> OperationsBriefingResponse:
    return build_operations_briefing(request)


@router.post(
    "/chat",
    responses={
        404: {"description": "Conversation not found for organization"},
        503: {"description": "AI provider unavailable"},
    },
)
async def chat(
    request: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    provider_router: Annotated[ProviderRouter, Depends(get_router)],
) -> ChatResponse:
    conversation = _get_or_create_conversation(db, request)
    retrieved = retrieve_context(db, organization_id=request.organization_id, query=request.message)
    context = format_context(retrieved)
    prompt = (
        "You are Lora, the Opslora tenant-aware business assistant.\n"
        "Use only the supplied tenant knowledge context and the user's message.\n"
        "If the context is insufficient, say what is missing instead of inventing facts.\n"
        "Return a concise business answer.\n\n"
        f"organization_id={request.organization_id}\n"
        f"user_id={request.user_id}\n\n"
        f"Tenant knowledge context:\n{context}\n\n"
        f"User message:\n{request.message}"
    )
    try:
        result, fallback_used = await provider_router.complete(prompt, allow_fallback=request.use_fallback)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"AI provider unavailable: {exc}") from exc

    citations = citations_for(retrieved)
    db.add(
        AIMessage(
            organization_id=request.organization_id,
            created_by_user_id=request.user_id,
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )
    )
    db.add(
        AIMessage(
            organization_id=request.organization_id,
            created_by_user_id=request.user_id,
            conversation_id=conversation.id,
            role="assistant",
            content=result.text,
            provider=result.provider,
            model=result.model,
            citations_json=[citation.model_dump() for citation in citations],
        )
    )
    db.add(
        AIUsageEvent(
            organization_id=request.organization_id,
            created_by_user_id=request.user_id,
            provider=result.provider,
            model=result.model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_micros=0,
        )
    )
    db.commit()

    return ChatResponse(
        provider=result.provider,
        model=result.model,
        response=result.text,
        fallback_used=fallback_used,
        conversation_id=conversation.id,
        citations=citations,
    )


def _get_or_create_conversation(db: Session, request: ChatRequest) -> AIConversation:
    if request.conversation_id:
        conversation = db.get(AIConversation, request.conversation_id)
        if conversation and conversation.organization_id == request.organization_id:
            return conversation
        raise HTTPException(status_code=404, detail="Conversation not found for organization")

    conversation = AIConversation(
        organization_id=request.organization_id,
        created_by_user_id=request.user_id,
        title=request.message[:120],
        status="active",
        metadata_json=None,
    )
    db.add(conversation)
    db.flush()
    return conversation
