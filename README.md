# DocMorph AI Engine

## Overview

DocMorph AI Engine is a FastAPI service for uploading handwritten PDF documents, extracting student records with Gemini, and generating Excel workbooks.

## Production-readiness improvements

- Added centralized configuration through Pydantic settings and .env-based environment management.
- Introduced SQLAlchemy models and Alembic migrations for jobs, uploads, extraction results, logs, and downloads.
- Added structured logging, validation, and consistent error envelope responses.
- Added storage management for uploads/results/temp/logs with cleanup rules.
- Preserved the existing upload, status, result, download, and delete APIs.

## Environment variables

- GEMINI_API_KEY
- DATABASE_URL
- UPLOAD_DIR
- RESULT_DIR
- TEMP_DIR
- LOG_DIR
- MAX_UPLOAD_SIZE_MB
- LOG_LEVEL
- CORS_ALLOWED_ORIGINS

## Run locally

```bash
python -m uvicorn main:app --reload
```

## Run tests

```bash
pytest -q
```

## Database migration

```bash
alembic upgrade head
```
