import os

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from main import app

client = TestClient(app)


def test_register_and_login_flow() -> None:
    email = "auth-user@example.com"
    response = client.post(
        "/auth/register",
        json={"name": "Auth User", "email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert "refresh_token" in payload

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login_response.status_code == 200


def test_protected_endpoint_requires_auth() -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
