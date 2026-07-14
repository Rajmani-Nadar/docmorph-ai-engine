from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(50), default="queued")
    current_step: Mapped[str] = mapped_column(String(100), default="Queued")
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_excel_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    student_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admission_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dob: Mapped[str | None] = mapped_column(String(100), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
