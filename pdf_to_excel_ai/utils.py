from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from config import BASE_DIR

EXPECTED_COLUMNS = [
    "S.No",
    "Student Name",
    "Photo No",
    "Class",
    "Father Name",
    "Mobile Number",
    "DOB",
    "Blood Group",
    "Address",
]

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> logging.Logger:
    """Configure file and console logging for the pipeline."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pdf_to_excel_ai")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def clean_json_response(text: str) -> str:
    """Extract the first valid JSON array while stripping markdown and surrounding prose."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Empty response received from Gemini.")

    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"`+", "", cleaned)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)
    cleaned = cleaned.strip()

    array_matches = re.findall(r"(\[[\s\S]*?\])", cleaned, flags=re.DOTALL)
    if not array_matches:
        raise ValueError("No JSON array found in Gemini response.")

    first_candidate = array_matches[0].strip()
    return first_candidate


def clean_json(text: str) -> str:
    """Backward-compatible wrapper for JSON cleanup."""
    return clean_json_response(text)


def validate_json(text: str) -> Any:
    """Validate and parse JSON returned by Gemini."""
    print(f"Raw Gemini response:\n{text}")
    cleaned = clean_json_response(text)
    return json.loads(cleaned)


def parse_records(payload: Any) -> list[dict[str, str]]:
    """Normalize Gemini JSON into a list of student record dictionaries."""
    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            records = payload["records"]
        elif isinstance(payload.get("students"), list):
            records = payload["students"]
        else:
            records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Gemini response did not contain a JSON array or object.")

    normalized_records: list[dict[str, str]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        normalized: dict[str, str] = {}
        for column in EXPECTED_COLUMNS:
            value = item.get(column, "")
            if value is None:
                normalized[column] = ""
            elif isinstance(value, str):
                normalized[column] = value.strip()
            else:
                normalized[column] = str(value).strip()
        normalized_records.append(normalized)

    return normalized_records
