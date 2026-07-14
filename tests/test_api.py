import uuid

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def _new_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user() -> str:
    email = _new_email()
    response = client.post(
        "/auth/register",
        json={"name": "API Test User", "email": email, "password": "secret123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "database" in payload
    assert "gemini" in payload


def test_upload_rejects_non_pdf() -> None:
    access_token = _create_user()
    response = client.post(
        "/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
        headers=_auth_header(access_token),
    )
    assert response.status_code == 400


def test_upload_rejects_empty_pdf_bytes() -> None:
    access_token = _create_user()
    response = client.post(
        "/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        headers=_auth_header(access_token),
    )
    assert response.status_code == 400
