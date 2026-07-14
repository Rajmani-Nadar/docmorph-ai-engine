from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from core.exceptions import AppError
from core.config import MAX_UPLOAD_SIZE_MB


def validate_upload(file_name: str | None, content: bytes) -> tuple[str, Path]:
    if not file_name or not file_name.lower().endswith(".pdf"):
        raise AppError("Invalid PDF", status_code=400, error_code="invalid_pdf")
    if not content:
        raise AppError("Empty PDF uploaded", status_code=400, error_code="empty_pdf")
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise AppError("File exceeds 25MB limit", status_code=413, error_code="file_too_large")

    pdf_path = Path(file_name)
    try:
        PdfReader(BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise AppError("Corrupted or unreadable PDF", status_code=400, error_code="invalid_pdf", details={"reason": str(exc)}) from exc
    return pdf_path.name, pdf_path


from io import BytesIO
