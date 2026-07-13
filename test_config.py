import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent / "pdf_to_excel_ai"
sys.path.insert(0, str(PROJECT_DIR))

import config


def test_pdf_file_resolves_to_existing_pdf() -> None:
    assert config.PDF_FILE.exists(), f"Expected PDF file to exist: {config.PDF_FILE}"
