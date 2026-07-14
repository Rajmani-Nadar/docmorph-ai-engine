from __future__ import annotations

import shutil
import time
from pathlib import Path

from core.settings import settings


class StorageManager:
    def __init__(self) -> None:
        self.upload_dir = settings.get_upload_dir()
        self.result_dir = settings.get_result_dir()
        self.temp_dir = settings.get_temp_dir()
        self.log_dir = settings.get_log_dir()
        for directory in (self.upload_dir, self.result_dir, self.temp_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def ensure_directories(self) -> None:
        for directory in (self.upload_dir, self.result_dir, self.temp_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def save_upload_bytes(self, job_id: str, filename: str, content: bytes) -> Path:
        sanitized_name = Path(filename).name or "upload.pdf"
        destination = self.temp_dir / f"{job_id}_{sanitized_name}"
        destination.write_bytes(content)
        return destination

    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        cutoff = time.time() - (max_age_hours * 60 * 60)
        removed = 0
        for directory in (self.temp_dir, self.result_dir, self.log_dir):
            if not directory.exists():
                continue
            for path in directory.iterdir():
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    def remove_path(self, path: Path | None) -> None:
        if path and path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)


storage_manager = StorageManager()
