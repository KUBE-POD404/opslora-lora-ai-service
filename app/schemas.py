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
