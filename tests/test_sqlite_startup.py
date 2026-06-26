import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, initialize_sqlite_schema_if_needed, settings
from app.main import app


def test_sqlite_initializer_creates_ai_metadata_tables():
    if not settings.database_url.startswith("sqlite"):
        pytest.skip("SQLite startup initialization is only active for SQLite database URLs.")

    Base.metadata.drop_all(bind=engine)
    initialize_sqlite_schema_if_needed()

    table_names = set(Base.metadata.tables)
    assert "ai_knowledge_sources" in table_names
    assert "ai_knowledge_chunks" in table_names
    assert "ai_conversations" in table_names


def test_lifespan_initializes_sqlite_schema_for_runtime_app():
    if not settings.database_url.startswith("sqlite"):
        pytest.skip("SQLite startup initialization is only active for SQLite database URLs.")

    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert "ai_knowledge_sources" in Base.metadata.tables
