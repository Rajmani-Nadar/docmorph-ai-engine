from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from config import OUTPUT_EXCEL, PDF_FILE
from excel_writer import write_excel
from gemini_client import call_gemini
from pdf_processor import convert_pdf, image_to_png_bytes
from utils import setup_logging


def main() -> None:
    """Run the full PDF-to-Excel extraction pipeline."""
    logger = setup_logging()

    try:
        pages = convert_pdf(logger)
        all_records: list[dict[str, str]] = []

        for idx, page in enumerate(pages, start=1):
            logger.info("Reading page %s...", idx)
            try:
                image_bytes = image_to_png_bytes(page)
                logger.info("Sending page to Gemini...")
                page_records = call_gemini(image_bytes, logger, page_number=idx)
                all_records.extend(page_records)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Page %s failed: %s", idx, exc)
                continue

        if not all_records:
            logger.warning("No records extracted from the PDF.")

        output_path = write_excel(all_records, OUTPUT_EXCEL, logger)
        logger.info("Finished")
        logger.info("Output saved to %s", output_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
