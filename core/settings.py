from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


def _is_pytest_running() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING"):
        return True
    return any("pytest" in str(arg).lower() for arg in sys.argv)


def _default_database_url() -> str:
    if _is_pytest_running():
        return "sqlite:///:memory:"
    return "sqlite:///./docmorph.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / "pdf_to_excel_ai" / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="DocMorph AI Engine")
    app_version: str = Field(default="1.1.0")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    max_upload_size_mb: int = Field(default=25)
    upload_dir: str = Field(default=str(BASE_DIR / "uploads"))
    result_dir: str = Field(default=str(BASE_DIR / "results"))
    temp_dir: str = Field(default=str(BASE_DIR / "temp"))
    log_dir: str = Field(default=str(BASE_DIR / "logs"))
    cors_allowed_origins: str = Field(default="http://localhost:3000")
    gemini_api_key: str = Field(default="")
    database_url: str = Field(default_factory=_default_database_url)
    model_name: str = Field(default="gemini-3.5-flash")
    poppler_path: str | None = Field(default=None)
    razorpay_key_id: str = Field(default="")
    razorpay_key_secret: str = Field(default="")

    def get_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def get_upload_dir(self) -> Path:
        return Path(self.upload_dir).expanduser().resolve()

    def get_result_dir(self) -> Path:
        return Path(self.result_dir).expanduser().resolve()

    def get_temp_dir(self) -> Path:
        return Path(self.temp_dir).expanduser().resolve()

    def get_log_dir(self) -> Path:
        return Path(self.log_dir).expanduser().resolve()


settings = Settings()
