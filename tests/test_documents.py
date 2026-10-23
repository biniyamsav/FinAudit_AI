import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def pdf(content: bytes = b"%PDF-1.4 test"):
    return {"file": ("a.pdf", content, "application/pdf")}


def new_workspace() -> str:
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    return response.json()["id"]


def test_create_workspace():
    response = client.post("/api/v1/workspaces")
    assert response.status_code == 201
    assert response.json()["status"] == "active"


def test_duplicate_upload_returns_same_document():
    url = f"/api/v1/workspaces/{new_workspace()}/documents"
    first = client.post(url, files=pdf())
    second = client.post(url, files=pdf())
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_same_file_in_two_workspaces_creates_two_documents():
    first = client.post(f"/api/v1/workspaces/{new_workspace()}/documents", files=pdf())
    second = client.post(f"/api/v1/workspaces/{new_workspace()}/documents", files=pdf())
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_unsupported_file_type_rejected():
    url = f"/api/v1/workspaces/{new_workspace()}/documents"
    files = {"file": ("a.exe", b"x", "application/octet-stream")}
    assert client.post(url, files=files).status_code == 415


def test_empty_file_rejected():
    url = f"/api/v1/workspaces/{new_workspace()}/documents"
    assert client.post(url, files=pdf(b"")).status_code == 400


def test_unknown_workspace_returns_404():
    url = f"/api/v1/workspaces/{uuid.uuid4()}/documents"
    assert client.post(url, files=pdf()).status_code == 404