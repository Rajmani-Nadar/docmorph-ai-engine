from __future__ import annotations

import time
import uuid
from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from main import app

client = TestClient(app)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _new_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _wait_for_job_in_history(access_token: str, job_id: str, timeout: float = 5.0) -> list[dict[str, object]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get("/history", headers=_auth_header(access_token))
        if response.status_code == 200:
            items = response.json()
            if any(item.get("job_id") == job_id for item in items):
                return items
        time.sleep(0.2)
    raise AssertionError(f"Job {job_id} not found in history after {timeout} seconds")


def _create_user(name: str) -> tuple[str, str]:
    email = _new_email(name.lower())
    password = "secret123"
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"], payload["refresh_token"]


def _create_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return buffer.read()


def _upload_pdf(access_token: str) -> str:
    pdf_bytes = _create_pdf_bytes()
    response = client.post(
        "/upload",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        headers=_auth_header(access_token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "jobId" in data
    return data["jobId"]


def test_authorization_requires_authentication() -> None:
    response = client.get("/history")
    assert response.status_code == 401

    response = client.get("/dashboard")
    assert response.status_code == 401

    response = client.get("/result/invalid-job")
    assert response.status_code == 401

    response = client.get("/download/invalid-job")
    assert response.status_code == 401

    response = client.delete("/job/invalid-job")
    assert response.status_code == 401


def test_authorization_user_ownership_for_job_resources() -> None:
    access_token_a, _ = _create_user("UserA")
    access_token_b, _ = _create_user("UserB")

    job_id = _upload_pdf(access_token_a)

    history_items = _wait_for_job_in_history(access_token_a, job_id)
    assert any(item["job_id"] == job_id for item in history_items)

    history_b = client.get("/history", headers=_auth_header(access_token_b))
    assert history_b.status_code == 200
    assert all(item["job_id"] != job_id for item in history_b.json())

    dashboard_b = client.get("/dashboard", headers=_auth_header(access_token_b))
    assert dashboard_b.status_code == 200
    payload_b = dashboard_b.json()
    assert payload_b["total_pdfs"] == 0
    assert payload_b["recent_activity"] == []

    dashboard_a = client.get("/dashboard", headers=_auth_header(access_token_a))
    assert dashboard_a.status_code == 200
    assert payload_b["total_pdfs"] == 0
    payload_a = dashboard_a.json()
    assert payload_a["total_pdfs"] >= 1
    assert any(item["job_id"] == job_id for item in payload_a["recent_activity"])

    response = client.get(f"/result/{job_id}", headers=_auth_header(access_token_b))
    assert response.status_code == 403

    response = client.get(f"/download/{job_id}", headers=_auth_header(access_token_b))
    assert response.status_code == 403

    response = client.delete(f"/job/{job_id}", headers=_auth_header(access_token_b))
    assert response.status_code == 403

    invalid_job_id = "invalid-job-id"
    response = client.get(f"/result/{invalid_job_id}", headers=_auth_header(access_token_a))
    assert response.status_code == 404

    response = client.get(f"/download/{invalid_job_id}", headers=_auth_header(access_token_a))
    assert response.status_code == 404

    response = client.delete(f"/job/{invalid_job_id}", headers=_auth_header(access_token_a))
    assert response.status_code == 404
