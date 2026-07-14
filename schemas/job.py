from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: float | None = None
    database: str | None = None
    gemini: str | None = None
    diskSpace: str | None = None


class UploadResponse(BaseModel):
    jobId: str
    status: str


class StatusResponse(BaseModel):
    status: str
    progress: float
    stage: str
    message: str
    currentStep: str
    currentPage: int
    totalPages: int
    completedPages: int
    failedPages: int
    estimatedRemaining: str
    error: str | None = None


class ResultResponse(BaseModel):
    records: list[dict[str, Any]]
    confidence: str


class HistoryItemResponse(BaseModel):
    job_id: str
    filename: str
    status: str
    uploaded_at: str | None
    completed_at: str | None = None
    rows_extracted: int
    file_size: int


class DashboardResponse(BaseModel):
    today_uploads: int
    total_pdfs: int
    average_processing_time: float
    total_downloads: int
    recent_activity: list[HistoryItemResponse]
    monthly_usage: dict[str, int]


class DeleteResponse(BaseModel):
    success: bool
    message: str
