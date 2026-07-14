from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class JobRecord:
    job_id: str
    input_path: Path | None = None
    output_path: Path | None = None
    result_path: Path | None = None
    status: str = "queued"
    progress: float = 0.0
    current_step: str = "Queued"
    current_page: int = 0
    total_pages: int = 0
    estimated_remaining: str = "Calculating"
    error: str | None = None
    records: list[dict[str, Any]] = field(default_factory=list)
    user_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_status(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "progress": round(self.progress, 2),
            "currentStep": self.current_step,
            "currentPage": self.current_page,
            "totalPages": self.total_pages,
            "estimatedRemaining": self.estimated_remaining,
        }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()

    def create(self, job_id: str, input_path: Path | None = None, user_id: int | None = None) -> JobRecord:
        with self._lock:
            record = JobRecord(job_id=job_id, input_path=input_path, user_id=user_id)
            self._jobs[job_id] = record
            return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **updates: Any) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            for key, value in updates.items():
                setattr(record, key, value)
            record.updated_at = datetime.now(timezone.utc)
            return record

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


job_manager = JobStore()
