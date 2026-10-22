
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/v1/health")

    assert response.status_code == 200


def test_health_response_schema():
    response = client.get("/api/v1/health")

    assert response.json() == {"status": "ok"}
