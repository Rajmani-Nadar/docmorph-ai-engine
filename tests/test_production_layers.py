from __future__ import annotations

from pathlib import Path

from core.config import RESULT_DIR, TEMP_DIR
from core.exceptions import AppError
from storage.manager import storage_manager
from app_utils.validation import validate_upload


def test_storage_manager_creates_required_directories() -> None:
    for path in (TEMP_DIR, RESULT_DIR, storage_manager.log_dir):
        assert Path(path).exists()


def test_validate_upload_rejects_empty_pdf() -> None:
    try:
        validate_upload("empty.pdf", b"")
    except AppError as exc:
        assert exc.error_code == "empty_pdf"
    else:
        raise AssertionError("Expected empty upload to raise AppError")


def test_validate_upload_rejects_invalid_extension() -> None:
    try:
        validate_upload("file.txt", b"payload")
    except AppError as exc:
        assert exc.error_code == "invalid_pdf"
    else:
        raise AssertionError("Expected invalid extension to raise AppError")
