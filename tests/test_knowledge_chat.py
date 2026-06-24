from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.providers.base import CompletionResult
from app.routers.v1.ai import get_router
from app.services.knowledge import retrieve_context


class FakeProviderRouter:
    async def health(self):
        return []

    async def complete(self, prompt: str, *, allow_fallback: bool = True):
        assert "Tenant knowledge context" in prompt
        assert "renewal risk" in prompt
        return CompletionResult(
            provider="fake",
            model="unit-test",
            text="The customer has renewal risk because adoption dropped.",
        ), False


def test_ingest_knowledge_and_chat_returns_citations():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_router] = lambda: FakeProviderRouter()
    client = TestClient(app)
    organization_id = f"org-{uuid.uuid4()}"

    ingest_response = client.post(
        "/api/v1/ai/knowledge/sources",
        json={
            "organization_id": organization_id,
            "user_id": "user-1",
            "source_type": "note",
            "source_uri": "crm://accounts/acme",
            "title": "Acme renewal note",
            "content": "Acme has renewal risk because product adoption dropped in Q4.",
        },
    )
    assert ingest_response.status_code == 200
    ingest_body = ingest_response.json()
    assert ingest_body["status"] == "indexed"
    assert ingest_body["chunks_created"] == 1

    chat_response = client.post(
        "/api/v1/ai/chat",
        json={
            "organization_id": organization_id,
            "user_id": "user-1",
            "message": "What is the renewal risk for Acme?",
            "use_fallback": False,
        },
    )
    assert chat_response.status_code == 200
    chat_body = chat_response.json()
    assert chat_body["provider"] == "fake"
    assert chat_body["conversation_id"]
    assert chat_body["citations"][0]["source_id"] == ingest_body["source_id"]
    assert "adoption dropped" in chat_body["citations"][0]["snippet"]

    app.dependency_overrides.clear()


def test_retrieval_prefers_exact_term_matches():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    organization_id = f"org-{uuid.uuid4()}"

    for content in (
        "The brisket lunch note is unrelated.",
        "The customer has renewal risk because adoption dropped.",
    ):
        response = client.post(
            "/api/v1/ai/knowledge/sources",
            json={
                "organization_id": organization_id,
                "user_id": "user-1",
                "source_type": "note",
                "content": content,
            },
        )
        assert response.status_code == 200

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        retrieved = retrieve_context(db, organization_id=organization_id, query="renewal risk")
    finally:
        db.close()

    assert retrieved
    assert "renewal risk" in retrieved[0].chunk.content.lower()
