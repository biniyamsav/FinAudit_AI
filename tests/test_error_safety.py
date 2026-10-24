
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def test_debug_defaults_to_false():
    assert Settings.model_fields["debug"].default is False


@pytest.mark.parametrize("environment", ["development", "testing"])
def test_unhandled_error_returns_safe_json(monkeypatch, environment):
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()
    try:
        app = create_app()

        @app.get("/error_safety_probe")
        def probe():
            raise RuntimeError("secret-internal-detail")

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/error_safety_probe")

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error."}
        assert "Traceback" not in response.text
        assert "secret-internal-detail" not in response.text
        assert ".py" not in response.text
        assert "C:\\" not in response.text
    finally:
        get_settings.cache_clear()
