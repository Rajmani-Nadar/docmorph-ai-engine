from __future__ import annotations

from datetime import datetime
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database.models import Job, MonthlyUsage, UploadedFile, ExtractionResult, ProcessingLog, Download


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(self, *, job_id: str, filename: str, original_filename: str, file_size: int, user_id: int | None = None) -> Job:
        job = Job(
            job_id=job_id,
            filename=filename,
            original_filename=original_filename,
            file_size=file_size,
            processing_status="queued",
            user_id=user_id,
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def update_job(self, job_id: str, **values: object) -> Job | None:
        job = self.session.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return None
        for key, value in values.items():
            setattr(job, key, value)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self.session.query(Job).filter(Job.job_id == job_id).first()

    def get_job_for_user(self, job_id: str, user_id: int) -> Job | None:
        return self.session.query(Job).filter(Job.job_id == job_id, Job.user_id == user_id).first()

    def get_jobs_for_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Job]:
        return (
            self.session.query(Job)
            .filter(Job.user_id == user_id)
            .order_by(Job.upload_time.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_dashboard_stats_for_user(self, user_id: int) -> dict[str, object]:
        jobs = self.session.query(Job).filter(Job.user_id == user_id).all()
        total_pdfs = len(jobs)
        completed_durations = [
            (job.completed_time - job.upload_time).total_seconds()
            for job in jobs
            if job.upload_time and job.completed_time
        ]
        average_processing_time = round(sum(completed_durations) / len(completed_durations), 2) if completed_durations else 0
        monthly_usage = self.session.query(MonthlyUsage).filter(
            MonthlyUsage.user_id == user_id,
            MonthlyUsage.year == datetime.utcnow().year,
            MonthlyUsage.month == datetime.utcnow().month,
        ).first()
        monthly_usage_payload = {
            "uploads": monthly_usage.uploads_used if monthly_usage else 0,
            "pages": monthly_usage.pages_processed if monthly_usage else 0,
            "excelDownloads": monthly_usage.excel_downloads if monthly_usage else 0,
            "csvDownloads": monthly_usage.csv_downloads if monthly_usage else 0,
            "processingTimeSeconds": monthly_usage.processing_time_seconds if monthly_usage else 0,
        }
        total_downloads = (monthly_usage.excel_downloads + monthly_usage.csv_downloads) if monthly_usage else 0
        recent_activity = [
            {
                "job_id": job.job_id,
                "filename": job.original_filename or job.filename,
                "status": job.processing_status,
                "uploaded_at": job.upload_time.isoformat() if job.upload_time else None,
                "completed_at": job.completed_time.isoformat() if job.completed_time else None,
                "rows_extracted": 0,
                "file_size": job.file_size,
            }
            for job in sorted(jobs, key=lambda job: job.upload_time or job.upload_time, reverse=True)[:5]
        ]
        return {
            "today_uploads": sum(1 for job in jobs if job.upload_time and job.upload_time.date() == datetime.utcnow().date()),
            "total_pdfs": total_pdfs,
            "average_processing_time": average_processing_time,
            "total_downloads": total_downloads,
            "recent_activity": recent_activity,
            "monthly_usage": monthly_usage_payload,
        }

    def save_upload(self, *, job_id: str, storage_path: str, content_type: str | None, size_bytes: int) -> UploadedFile:
        upload = UploadedFile(job_id=job_id, storage_path=storage_path, content_type=content_type, size_bytes=size_bytes)
        self.session.add(upload)
        self.session.commit()
        self.session.refresh(upload)
        return upload

    def save_result(self, *, job_id: str, record: dict[str, object]) -> ExtractionResult:
        result = ExtractionResult(
            job_id=job_id,
            student_name=str(record.get("Student Name", "") or ""),
            father_name=str(record.get("Father Name", "") or ""),
            admission_number=str(record.get("Admission Number", "") or ""),
            class_name=str(record.get("Class", "") or ""),
            dob=str(record.get("DOB", "") or ""),
            blood_group=str(record.get("Blood Group", "") or ""),
            mobile_number=str(record.get("Mobile Number", "") or ""),
            address=str(record.get("Address", "") or ""),
            confidence=str(record.get("Confidence", "") or ""),
        )
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def save_log(self, *, job_id: str, level: str, message: str) -> ProcessingLog:
        log = ProcessingLog(job_id=job_id, level=level, message=message)
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def save_download(self, *, job_id: str, path: str) -> Download:
        download = Download(job_id=job_id, path=path)
        self.session.add(download)
        self.session.commit()
        self.session.refresh(download)
        return download
