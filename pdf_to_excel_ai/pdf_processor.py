from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image
from pdf2image import convert_from_path

try:
    from .config import PDF_FILE, POPPLER_PATH
except ImportError:  # pragma: no cover - fallback for direct script execution
    from config import PDF_FILE, POPPLER_PATH


def convert_pdf(logger: logging.Logger, pdf_path: str | Path | None = None) -> list[Image.Image]:
    """Convert a PDF file into a list of PIL images at 300 DPI."""
    logger.info("Converting PDF...")

    resolved_path = Path(pdf_path).resolve() if pdf_path is not None else PDF_FILE
    if not resolved_path.exists():
        raise FileNotFoundError(f"PDF file not found: {resolved_path}")

    conversion_kwargs: dict[str, Any] = {"dpi": 300}
    if POPPLER_PATH is not None:
        conversion_kwargs["poppler_path"] = str(POPPLER_PATH)

    pages = convert_from_path(str(resolved_path), **conversion_kwargs)
    if not pages:
        raise ValueError("No pages were extracted from the supplied PDF.")

    return pages


def image_to_png_bytes(image: Image.Image) -> bytes:
    """Convert a PIL image to PNG bytes without writing any temporary files."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
