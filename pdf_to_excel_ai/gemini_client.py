from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, MODEL_NAME
from utils import LOG_DIR, EXPECTED_COLUMNS, parse_records, validate_json


PROMPT = (
    "Extract handwritten student records from the provided image. "
    "Return ONLY JSON. "
    "Expected columns: "
    "S.No, Student Name, Photo No, Class, Father Name, Mobile Number, DOB, Blood Group, Address. "
    "Rules: do not explain, do not wrap markdown, keep spelling exactly as written, "
    "if unreadable return empty string, never skip students. "
    "Return a JSON array of objects where each object contains the exact column names above."
)

STRICT_PROMPT = "Return ONLY valid JSON. Do not explain. Do not use markdown."


def _extract_text(response: Any) -> str:
    """Extract raw text content from the Gemini response object."""
    if isinstance(response, str):
        return response

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None)
    if candidates:
        first_candidate = candidates[0]
        content = getattr(first_candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                return part_text

    return str(response)


def _build_model_candidates(configured_model: str) -> list[str]:
    """Build a robust list of current Gemini model aliases to try."""
    candidates: list[str] = []
    seen: set[str] = set()
    for model_name in [configured_model, "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
        if model_name and model_name not in seen:
            candidates.append(model_name)
            seen.add(model_name)
    return candidates


def _should_fallback(error_text: str, model_name: str) -> bool:
    lowered = error_text.lower()
    return any(
        marker in lowered for marker in ("not found", "404", "unsupported", "unavailable", "invalid model")
    ) and model_name != "gemini-flash-latest"


def _save_invalid_response(raw_text: str, page_number: int, logger: logging.Logger) -> None:
    """Persist the raw Gemini response when JSON parsing fails."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    output_path = LOG_DIR / f"invalid_response_page_{page_number}.txt"
    output_path.write_text(raw_text, encoding="utf-8")
    logger.warning("Saved invalid Gemini response to %s", output_path)


def call_gemini(image_bytes: bytes, logger: logging.Logger, page_number: int = 1) -> list[dict[str, str]]:
    """Send a page image to Gemini and parse records while tolerating malformed replies."""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is missing. Add it to the .env file.")
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)
    candidate_models = _build_model_candidates(MODEL_NAME)
    prompts = [PROMPT, STRICT_PROMPT]

    for prompt_index, prompt_text in enumerate(prompts, start=1):
        for model_name in candidate_models:
            try:
                logger.info("Sending page to Gemini with model %s...", model_name)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=prompt_text),
                    ],
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                text = _extract_text(response)
                payload = validate_json(text)
                records = parse_records(payload)
                logger.info("JSON Parsed")
                return records
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON for page %s with %s: %s", page_number, model_name, exc)
                _save_invalid_response(text if "text" in locals() else "", page_number, logger)
                if prompt_index == 1:
                    logger.warning("Retrying page %s with a stricter prompt", page_number)
                    break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini attempt for page %s with %s failed: %s", page_number, model_name, exc)
                if _should_fallback(str(exc), model_name):
                    break

        if prompt_index == 1:
            time.sleep(2)

    logger.warning("Skipping page %s because Gemini did not return usable JSON", page_number)
    return []
