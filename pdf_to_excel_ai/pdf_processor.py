from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from PIL import Image
from pdf2image import convert_from_path

from config import PDF_FILE, POPPLER_PATH


def convert_pdf(logger: logging.Logger) -> list[Image.Image]:
    """Convert the PDF file into a list of PIL images at 300 DPI."""
    logger.info("Converting PDF...")

    if not PDF_FILE.exists():
        raise FileNotFoundError(f"PDF file not found: {PDF_FILE}")

    conversion_kwargs: dict[str, Any] = {"dpi": 300}
    if POPPLER_PATH is not None:
        conversion_kwargs["poppler_path"] = str(POPPLER_PATH)

    pages = convert_from_path(str(PDF_FILE), **conversion_kwargs)
    if not pages:
        raise ValueError("No pages were extracted from the supplied PDF.")

    return pages


def image_to_png_bytes(image: Image.Image) -> bytes:
    """Convert a PIL image to PNG bytes without writing any temporary files."""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
