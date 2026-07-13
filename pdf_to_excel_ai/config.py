from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def resolve_path(value: str | os.PathLike[str], default: Path) -> Path:
    """Resolve a path from the environment relative to the project directory."""
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path.resolve()

    candidates = [BASE_DIR / path, BASE_DIR.parent / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (BASE_DIR / path).resolve()


DEFAULT_PDF_FILE = (BASE_DIR / "vi b idcard details.pdf").resolve()
if not DEFAULT_PDF_FILE.exists():
    alt_default = (BASE_DIR.parent / "vi b idcard details.pdf").resolve()
    if alt_default.exists():
        DEFAULT_PDF_FILE = alt_default

PDF_FILE = resolve_path(os.getenv("PDF_FILE", str(DEFAULT_PDF_FILE)), DEFAULT_PDF_FILE)
if not PDF_FILE.exists() and PDF_FILE.name:
    fallback = (BASE_DIR / PDF_FILE.name).resolve()
    if fallback.exists():
        PDF_FILE = fallback

OUTPUT_EXCEL = resolve_path(os.getenv("OUTPUT_EXCEL", str(BASE_DIR / "VI_B_IDCard_Details.xlsx")), BASE_DIR / "VI_B_IDCard_Details.xlsx")

RAW_POPPLER_PATH = os.getenv("POPPLER_PATH", "")
POPPLER_PATH = resolve_path(RAW_POPPLER_PATH, BASE_DIR) if RAW_POPPLER_PATH else None

MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
