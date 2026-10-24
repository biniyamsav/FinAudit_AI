from fastapi.testclient import TestClient

from app.main import ALLOWED_ORIGINS, app

client = TestClient(app)


def test_health_keeps_exact_liveness_payload():
    """The liveness contract is pre-existing and must stay byte-stable."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_postgres_weaviate_and_groq():
    response = client.get("/api/v1/health/status")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    by_name = {d["name"]: d for d in body["dependencies"]}
    assert set(by_name) == {"postgresql", "weaviate", "groq"}
    assert by_name["postgresql"]["status"] == "ok"
    assert by_name["weaviate"]["status"] == "ok"


def test_status_reports_groq_as_configuration_not_a_live_ping(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    groq = next(
        d
        for d in client.get("/api/v1/health/status").json()["dependencies"]
        if d["name"] == "groq"
    )
    assert groq["status"] == "not_configured"
    assert "GROQ_API_KEY" in groq["detail"]


def test_status_never_leaks_credentials(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_super_secret_value")
    body = client.get("/api/v1/health/status").json()
    assert "gsk_super_secret_value" not in str(body)


def test_cors_allows_the_local_frontend_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_the_configured_origins_only():
    assert "http://localhost:3000" in ALLOWED_ORIGINS
    assert "*" not in ALLOWED_ORIGINS

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    # A disallowed origin gets no allow-origin grant back.
    assert response.headers.get("access-control-allow-origin") != "http://evil.example"
