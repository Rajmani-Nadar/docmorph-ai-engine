# C:\Users\Vihasini\OneDrive\Desktop\handwritten-pdf-to-excel-ai\main.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from time import time

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parent
PDF_MODULE_DIR = ROOT_DIR / "pdf_to_excel_ai"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PDF_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(PDF_MODULE_DIR))

from auth.dependencies import get_current_user
from auth.routes import router as auth_router
from core.config import CORS_ORIGINS, HOST, MAX_UPLOAD_SIZE_MB, PORT, VERSION, ensure_directories
from core.exceptions import AppError, register_exception_handlers
from database.base import Base
from database.session import SessionLocal, engine
from repositories.job_repository import JobRepository
from schemas.job import DeleteResponse, DashboardResponse, HealthResponse, HistoryItemResponse, ResultResponse, StatusResponse, UploadResponse
from services.processing import processing_service
from services.payments import PaymentService
from services.subscription import BillingService, PlanService, SubscriptionService, UsageService
from auth.dependencies import get_db
from sqlalchemy.orm import Session
from storage.manager import storage_manager
from app_utils.validation import validate_upload

app = FastAPI(title="DocMorph AI Engine", version=VERSION, docs_url="/docs", redoc_url="/redoc")
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)

START_TIME = time()


@app.on_event("startup")
async def startup_event() -> None:
    ensure_directories()
    storage_manager.ensure_directories()
    Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(users);"))
            columns = [row[1] for row in result.fetchall()]
            if "token_version" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
            for column_name in ("current_plan", "subscription_status", "billing_status", "renewal_date"):
                if column_name not in columns:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} TEXT"))
    except Exception:
        pass
    processing_service.cleanup_old_files()
    # Ensure seed plans using a managed DB session so it is closed afterwards
    from database.session import SessionLocal

    with SessionLocal() as session:
        PlanService(session).ensure_seed_plans()


@app.get("/", response_model=dict)
async def root() -> dict[str, str]:
    return {"service": "DocMorph AI Engine", "status": "running"}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    disk_usage = os.statvfs(str(storage_manager.get_temp_dir())) if hasattr(os, "statvfs") else None
    disk_free_gb = round((disk_usage.f_bavail * disk_usage.f_frsize) / (1024**3), 2) if disk_usage else 0.0
    return HealthResponse(
        status="healthy",
        version=VERSION,
        uptime=round(time() - START_TIME, 2),
        database="ready",
        gemini="configured" if os.getenv("GEMINI_API_KEY", "") else "not-configured",
        diskSpace=f"{disk_free_gb:.2f} GB free",
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict[str, object] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not file.filename:
        raise AppError("Filename is required", status_code=400, error_code="invalid_filename")
    content = await file.read()
    validate_upload(file.filename, content)

    usage_service = UsageService(db)
    quota_result = usage_service.enforce_upload_quota(int(current_user["id"]), size_bytes=len(content), pages=1)
    if not quota_result["success"]:
        raise AppError(quota_result["message"], status_code=402, error_code=quota_result["errorCode"], details={"recommendedPlan": quota_result.get("recommendedPlan")})

    usage_service.record_upload(int(current_user["id"]), size_bytes=len(content))
    job_id, file_path = processing_service.create_upload_job_from_bytes(file.filename, content, user_id=int(current_user["id"]))
    processing_service.attach_job_user(job_id, int(current_user["id"]))
    background_tasks.add_task(processing_service.start_processing, job_id, file_path)
    return UploadResponse(jobId=job_id, status="processing")


def verify_job_ownership(job_id: str, user_id: int) -> None:
    with SessionLocal() as session:
        repository = JobRepository(session)
        job = repository.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if job.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str, current_user: dict[str, object] = Depends(get_current_user)) -> StatusResponse:
    verify_job_ownership(job_id, int(current_user["id"]))
    status_payload = processing_service.get_status(job_id)
    if not status_payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return StatusResponse(**status_payload)


@app.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str, current_user: dict[str, object] = Depends(get_current_user)) -> ResultResponse:
    verify_job_ownership(job_id, int(current_user["id"]))
    result_payload = processing_service.get_result(job_id)
    if result_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    status_payload = processing_service.get_status(job_id)
    if status_payload and status_payload.get("status") == "failed":
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=status_payload.get("error") or "Processing failed")
    return ResultResponse(records=result_payload, confidence="medium")
    result_payload = processing_service.get_result(job_id)
    if result_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    status_payload = processing_service.get_status(job_id)
    if status_payload and status_payload.get("status") == "failed":
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=status_payload.get("error") or "Processing failed")
    return ResultResponse(records=result_payload, confidence="medium")


@app.get("/download/{job_id}")
async def download_result(job_id: str, current_user: dict[str, object] = Depends(get_current_user)) -> FileResponse:
    verify_job_ownership(job_id, int(current_user["id"]))
    output_path = processing_service.get_download_path(job_id)
    if not output_path or not output_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    with SessionLocal() as session:
        repository = JobRepository(session)
        repository.save_download(job_id=job_id, path=str(output_path))
        UsageService(session).record_excel_download(int(current_user["id"]))
    return FileResponse(output_path, filename=output_path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/history", response_model=list[HistoryItemResponse])
async def get_history(current_user: dict[str, object] = Depends(get_current_user), limit: int = 50, offset: int = 0) -> list[HistoryItemResponse]:
    with SessionLocal() as session:
        repository = JobRepository(session)
        jobs = repository.get_jobs_for_user(int(current_user["id"]), limit=limit, offset=offset)
        return [
            HistoryItemResponse(
                job_id=job.job_id,
                filename=job.original_filename or job.filename,
                status=job.processing_status,
                uploaded_at=job.upload_time.isoformat() if job.upload_time else None,
                completed_at=job.completed_time.isoformat() if job.completed_time else None,
                rows_extracted=0,
                file_size=job.file_size,
            )
            for job in jobs
        ]


@app.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(current_user: dict[str, object] = Depends(get_current_user)) -> DashboardResponse:
    with SessionLocal() as session:
        repository = JobRepository(session)
        stats = repository.get_dashboard_stats_for_user(int(current_user["id"]))
        return DashboardResponse(**stats)


@app.delete("/job/{job_id}", response_model=DeleteResponse)
async def delete_job(job_id: str, current_user: dict[str, object] = Depends(get_current_user)) -> DeleteResponse:
    verify_job_ownership(job_id, int(current_user["id"]))
    deleted = processing_service.cancel_job(job_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return DeleteResponse(success=True, message="Job cancelled")


@app.get("/subscription")
async def get_subscription(current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = SubscriptionService(db)
    return service.get_subscription(int(current_user["id"]))


@app.get("/usage")
async def get_usage(current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = UsageService(db)
    return service.get_usage_summary(int(current_user["id"]))


@app.get("/plans")
async def get_plans(db: Session = Depends(get_db)) -> dict[str, object]:
    service = PlanService(db)
    return {"plans": service.list_plans()}


@app.post("/subscription/change")
async def change_subscription(payload: dict[str, str], current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = SubscriptionService(db)
    plan_code = payload.get("planCode") or payload.get("plan") or "FREE"
    return service.change_plan(int(current_user["id"]), plan_code)


@app.get("/billing/history")
async def get_billing_history(current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = BillingService(db)
    return {"events": service.get_billing_history(int(current_user["id"]))}


@app.post("/payments/create-order")
async def create_payment_order(payload: dict[str, object], current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = PaymentService(db)
    return service.create_order(
        user_id=int(current_user["id"]),
        plan_code=str(payload.get("planCode") or payload.get("plan") or "PRO"),
        amount=float(payload.get("amount") or 0),
    )


@app.post("/payments/verify")
async def verify_payment(payload: dict[str, object], current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = PaymentService(db)
    return service.verify_payment(user_id=int(current_user["id"]), payload=payload)


@app.post("/payments/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    service = PaymentService(db)
    return await service.handle_webhook(request)


@app.get("/payments/history")
async def payment_history(current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = PaymentService(db)
    return {"payments": service.get_history(int(current_user["id"]))}


@app.get("/payments/invoice/{invoice_id}")
async def payment_invoice(invoice_id: int, current_user: dict[str, object] = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    service = PaymentService(db)
    return service.get_invoice(invoice_id, user_id=int(current_user["id"]))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
