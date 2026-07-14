from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import create_engine

from core.config import RESULT_DIR, ensure_directories
from core.settings import settings
from jobs.manager import job_manager
from pdf_to_excel_ai.excel_writer import write_excel
from pdf_to_excel_ai.gemini_client import call_gemini
from pdf_to_excel_ai.pdf_processor import convert_pdf, image_to_png_bytes
from repositories.job_repository import JobRepository
from storage.manager import storage_manager
from app_utils.logging import get_logger


class ProcessingService:
    def __init__(self) -> None:
        ensure_directories()
        self.logger = get_logger("docmorph.processing")
        self.engine = create_engine(settings.database_url, future=True)

    def create_upload_job(self, uploaded_file: UploadFile) -> tuple[str, Path]:
        content = uploaded_file.file.read()
        return self.create_upload_job_from_bytes(uploaded_file.filename or "upload.pdf", content)

    def create_upload_job_from_bytes(self, filename: str, content: bytes, user_id: int | None = None) -> tuple[str, Path]:
        job_id = str(uuid.uuid4())
        file_path = storage_manager.save_upload_bytes(job_id, filename, content)
        job_manager.create(job_id=job_id, input_path=file_path, user_id=user_id)
        self.logger.info("Created job %s for %s", job_id, filename)
        return job_id, file_path

    def attach_job_user(self, job_id: str, user_id: int) -> None:
        try:
            from database.session import SessionLocal

            session = SessionLocal()
            repository = JobRepository(session)
            repository.update_job(job_id, user_id=user_id)
            session.close()
        except Exception:  # noqa: BLE001
            self.logger.exception("Failed to attach user %s to job %s", user_id, job_id)

    def start_processing(self, job_id: str, file_path: Path) -> None:
        job_manager.update(job_id, status="processing", current_step="Uploading PDF", progress=5.0)
        self.logger.info("Starting processing for job %s", job_id)

        try:
            from database.session import SessionLocal

            session = SessionLocal()
            repository = JobRepository(session)
            job_record = job_manager.get(job_id)
            repository.create_job(
                job_id=job_id,
                filename=file_path.name,
                original_filename=file_path.name,
                file_size=file_path.stat().st_size,
                user_id=job_record.user_id if job_record else None,
            )
            repository.save_upload(job_id=job_id, storage_path=str(file_path), content_type="application/pdf", size_bytes=file_path.stat().st_size)
            session.close()

            job_manager.update(job_id, current_step="Converting PDF", progress=10.0)
            pages = convert_pdf(self.logger, pdf_path=file_path)
            job_manager.update(job_id, total_pages=len(pages), current_step="Reading PDF", progress=15.0)

            all_records: list[dict[str, str]] = []
            for idx, page in enumerate(pages, start=1):
                job_manager.update(
                    job_id,
                    current_step=f"Reading Page {idx}",
                    current_page=idx,
                    progress=15.0 + (70.0 * idx / max(len(pages), 1)),
                    estimated_remaining=f"{max(len(pages) - idx, 0)} pages left",
                )
                self.logger.info("Reading page %s...", idx)
                image_bytes = image_to_png_bytes(page)
                self.logger.info("Sending page to Gemini...")
                page_records = call_gemini(image_bytes, self.logger, page_number=idx)
                all_records.extend(page_records)

            if not all_records:
                self.logger.warning("No records extracted from the PDF.")

            job_manager.update(job_id, current_step="Generating Excel", progress=90.0)
            output_path = write_excel(all_records, RESULT_DIR / f"{job_id}.xlsx", self.logger)
            job_manager.update(
                job_id,
                status="completed",
                current_step="Preparing Download",
                progress=100.0,
                output_path=output_path,
                result_path=output_path,
                records=all_records,
                estimated_remaining="Completed",
            )

            session = SessionLocal()
            repository = JobRepository(session)
            repository.update_job(job_id, processing_status="completed", current_step="Preparing Download", progress=100.0, output_excel_path=str(output_path))
            for record in all_records:
                repository.save_result(job_id=job_id, record=record)
            repository.save_log(job_id=job_id, level="INFO", message="Processing completed")
            session.close()
            self.logger.info("Finished job %s", job_id)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Pipeline failed for job %s: %s", job_id, exc)
            job_manager.update(
                job_id,
                status="failed",
                current_step="Failed",
                progress=100.0,
                error=str(exc),
                estimated_remaining="Failed",
            )
            try:
                session = SessionLocal()
                repository = JobRepository(session)
                repository.update_job(job_id, processing_status="failed", current_step="Failed", progress=100.0, error_message=str(exc))
                repository.save_log(job_id=job_id, level="ERROR", message=str(exc))
                session.close()
            except Exception:  # noqa: BLE001
                self.logger.exception("Failed to persist processing failure for job %s", job_id)

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        job = job_manager.get(job_id)
        if not job:
            return None
        return job.to_status() | {"status": job.status, "error": job.error}

    def get_result(self, job_id: str) -> list[dict[str, Any]] | None:
        job = job_manager.get(job_id)
        if not job:
            return None
        return job.records

    def get_download_path(self, job_id: str) -> Path | None:
        job = job_manager.get(job_id)
        if not job:
            return None
        return job.output_path

    def cancel_job(self, job_id: str) -> bool:
        job = job_manager.get(job_id)
        if not job:
            return False
        storage_manager.remove_path(job.input_path)
        storage_manager.remove_path(job.output_path)
        job_manager.delete(job_id)
        return True

    def cleanup_old_files(self) -> None:
        storage_manager.cleanup_temp_files()


processing_service = ProcessingService()
