from __future__ import annotations

from pathlib import Path

from core.settings import settings

BASE_DIR = Path(__file__).resolve().parents[1]

HOST = settings.host
PORT = settings.port
MAX_UPLOAD_SIZE_MB = settings.max_upload_size_mb
VERSION = settings.app_version
CORS_ORIGINS = settings.get_cors_origins()

UPLOAD_DIR = settings.get_upload_dir()
RESULT_DIR = settings.get_result_dir()
TEMP_DIR = settings.get_temp_dir()
LOG_DIR = settings.get_log_dir()


def ensure_directories() -> None:
    for directory in (UPLOAD_DIR, RESULT_DIR, TEMP_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)


ensure_directories()
