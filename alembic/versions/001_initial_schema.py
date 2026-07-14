from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("upload_time", sa.DateTime(), nullable=False),
        sa.Column("started_time", sa.DateTime(), nullable=True),
        sa.Column("completed_time", sa.DateTime(), nullable=True),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("current_step", sa.String(length=100), nullable=False),
        sa.Column("current_page", sa.Integer(), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output_excel_path", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_job_id"), "jobs", ["job_id"], unique=True)

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_files")),
    )
    op.create_index(op.f("ix_uploaded_files_job_id"), "uploaded_files", ["job_id"], unique=False)

    op.create_table(
        "extraction_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("student_name", sa.String(length=255), nullable=True),
        sa.Column("father_name", sa.String(length=255), nullable=True),
        sa.Column("admission_number", sa.String(length=100), nullable=True),
        sa.Column("class_name", sa.String(length=100), nullable=True),
        sa.Column("dob", sa.String(length=100), nullable=True),
        sa.Column("blood_group", sa.String(length=50), nullable=True),
        sa.Column("mobile_number", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_results")),
    )
    op.create_index(op.f("ix_extraction_results_job_id"), "extraction_results", ["job_id"], unique=False)

    op.create_table(
        "processing_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_logs")),
    )
    op.create_index(op.f("ix_processing_logs_job_id"), "processing_logs", ["job_id"], unique=False)

    op.create_table(
        "downloads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_downloads")),
    )
    op.create_index(op.f("ix_downloads_job_id"), "downloads", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_downloads_job_id"), table_name="downloads")
    op.drop_index(op.f("ix_processing_logs_job_id"), table_name="processing_logs")
    op.drop_index(op.f("ix_extraction_results_job_id"), table_name="extraction_results")
    op.drop_index(op.f("ix_uploaded_files_job_id"), table_name="uploaded_files")
    op.drop_index(op.f("ix_jobs_job_id"), table_name="jobs")
    op.drop_table("downloads")
    op.drop_table("processing_logs")
    op.drop_table("extraction_results")
    op.drop_table("uploaded_files")
    op.drop_table("jobs")
