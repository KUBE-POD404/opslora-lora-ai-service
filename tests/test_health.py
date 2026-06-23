from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ai_health_ok():
    client = TestClient(app)
    response = client.get("/api/v1/ai/health")
    assert response.status_code == 200
    assert response.json()["service"] == "lora-ai"
