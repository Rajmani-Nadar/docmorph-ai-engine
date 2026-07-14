from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from auth.models import User
from core.config import MAX_UPLOAD_SIZE_MB
from database.models import BillingEvent, Invoice, MonthlyUsage, Payment, SubscriptionPlan, UsageRecord, UserSubscription
from database.session import SessionLocal
from core.exceptions import AppError


PLAN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "FREE": {
        "code": "FREE",
        "name": "Free",
        "description": "For personal use and light OCR tasks.",
        "max_uploads_per_month": 20,
        "max_pages_per_month": 100,
        "max_upload_size_mb": 10,
        "supports_priority_processing": False,
        "supports_csv_export": False,
        "supports_api_access": False,
        "supports_bulk_uploads": False,
        "supports_custom_branding": False,
        "history_days": 30,
    },
    "PRO": {
        "code": "PRO",
        "name": "Pro",
        "description": "For professionals who need higher throughput.",
        "max_uploads_per_month": None,
        "max_pages_per_month": None,
        "max_upload_size_mb": 25,
        "supports_priority_processing": True,
        "supports_csv_export": True,
        "supports_api_access": False,
        "supports_bulk_uploads": False,
        "supports_custom_branding": False,
        "history_days": None,
    },
    "ENTERPRISE": {
        "code": "ENTERPRISE",
        "name": "Enterprise",
        "description": "For teams with API, bulk, and premium support needs.",
        "max_uploads_per_month": None,
        "max_pages_per_month": None,
        "max_upload_size_mb": None,
        "supports_priority_processing": True,
        "supports_csv_export": True,
        "supports_api_access": True,
        "supports_bulk_uploads": True,
        "supports_custom_branding": True,
        "history_days": None,
    },
}


class PlanService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()
        self._plan_cache: dict[str, SubscriptionPlan] = {}
        self.ensure_seed_plans()

    def ensure_seed_plans(self) -> None:
        for payload in PLAN_DEFINITIONS.values():
            plan = self.session.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload["code"]).first()
            if not plan:
                self.session.add(
                    SubscriptionPlan(
                        code=payload["code"],
                        name=payload["name"],
                        description=payload["description"],
                        max_uploads_per_month=payload["max_uploads_per_month"],
                        max_pages_per_month=payload["max_pages_per_month"],
                        max_upload_size_mb=payload["max_upload_size_mb"],
                        supports_priority_processing=payload["supports_priority_processing"],
                        supports_csv_export=payload["supports_csv_export"],
                        supports_api_access=payload["supports_api_access"],
                        supports_bulk_uploads=payload["supports_bulk_uploads"],
                        supports_custom_branding=payload["supports_custom_branding"],
                        history_days=payload["history_days"],
                    )
                )
        self.session.commit()

    def get_plan(self, plan_code: str) -> SubscriptionPlan | None:
        plan_code = (plan_code or "FREE").upper()
        cached = self._plan_cache.get(plan_code)
        if cached:
            return cached
        plan = self.session.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
        if plan:
            self._plan_cache[plan_code] = plan
        return plan

    def list_plans(self) -> list[dict[str, Any]]:
        plans = self.session.query(SubscriptionPlan).order_by(SubscriptionPlan.code.asc()).all()
        return [self._serialize_plan(plan) for plan in plans]

    def get_effective_plan(self, user: User) -> SubscriptionPlan:
        sub = self.session.query(UserSubscription).filter(UserSubscription.user_id == user.id).order_by(UserSubscription.started_at.desc()).first()
        plan_code = sub.plan_code if sub else (user.current_plan or "FREE")
        plan = self.get_plan(plan_code) or self.get_plan("FREE")
        return plan

    def _serialize_plan(self, plan: SubscriptionPlan) -> dict[str, Any]:
        return {
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "maxUploadsPerMonth": plan.max_uploads_per_month,
            "maxPagesPerMonth": plan.max_pages_per_month,
            "maxUploadSizeMb": plan.max_upload_size_mb,
            "features": {
                "priorityProcessing": plan.supports_priority_processing,
                "csvExport": plan.supports_csv_export,
                "apiAccess": plan.supports_api_access,
                "bulkUploads": plan.supports_bulk_uploads,
                "customBranding": plan.supports_custom_branding,
            },
            "historyDays": plan.history_days,
        }

    def get_recommended_plan(self, current_plan_code: str, *, size_bytes: int | None = None) -> str:
        if size_bytes is not None and size_bytes > 10 * 1024 * 1024 and current_plan_code != "PRO":
            return "PRO"
        if current_plan_code == "FREE":
            return "PRO"
        return "ENTERPRISE"


class SubscriptionService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()
        self.plan_service = PlanService(self.session)
        self.billing_service = BillingService(self.session)

    def get_subscription(self, user_id: int) -> dict[str, Any]:
        user = self.session.query(User).get(user_id)
        if not user:
            raise AppError("User not found", status_code=404, error_code="user_not_found")
        subscription = self.session.query(UserSubscription).filter(UserSubscription.user_id == user_id).order_by(UserSubscription.started_at.desc()).first()
        plan_code = (subscription.plan_code if subscription else user.current_plan) or "FREE"
        plan = self.plan_service.get_plan(plan_code) or self.plan_service.get_plan("FREE")
        billing_status = self._resolve_billing_status(user_id, user)
        return {
            "planCode": plan.code,
            "currentPlan": plan.code,
            "planName": plan.name,
            "subscriptionStatus": user.subscription_status or ("active" if subscription else "inactive"),
            "billingStatus": billing_status,
            "renewalDate": user.renewal_date.isoformat() if user.renewal_date else None,
            "features": {
                "priorityProcessing": plan.supports_priority_processing,
                "csvExport": plan.supports_csv_export,
                "apiAccess": plan.supports_api_access,
                "bulkUploads": plan.supports_bulk_uploads,
                "customBranding": plan.supports_custom_branding,
            },
        }

    def _resolve_billing_status(self, user_id: int, user: User) -> str:
        if user.billing_status and user.billing_status.lower() != "pending":
            return user.billing_status
        invoice = self.session.query(Invoice).filter(Invoice.user_id == user_id).order_by(Invoice.issued_at.desc()).first()
        if invoice and invoice.status:
            return invoice.status
        payment = self.session.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.completed_at.desc()).first()
        if payment and payment.status:
            return payment.status
        return user.billing_status or "pending"

    def change_plan(self, user_id: int, plan_code: str) -> dict[str, Any]:
        plan_code = (plan_code or "FREE").upper()
        plan = self.plan_service.get_plan(plan_code)
        if not plan:
            raise AppError("Unsupported plan", status_code=400, error_code="unsupported_plan")

        user = self.session.query(User).get(user_id)
        if not user:
            raise AppError("User not found", status_code=404, error_code="user_not_found")

        subscription = self.session.query(UserSubscription).filter(UserSubscription.user_id == user_id).order_by(UserSubscription.started_at.desc()).first()
        if not subscription:
            subscription = UserSubscription(user_id=user_id, plan_code=plan.code, status="active", billing_status="pending", started_at=datetime.utcnow(), renewal_date=datetime.utcnow() + timedelta(days=30))
            self.session.add(subscription)
        else:
            subscription.plan_code = plan.code
            subscription.status = "active"
            subscription.billing_status = "pending"
            subscription.renewal_date = datetime.utcnow() + timedelta(days=30)
            subscription.started_at = subscription.started_at or datetime.utcnow()

        user.current_plan = plan.code
        user.subscription_status = "active"
        user.billing_status = "pending"
        user.renewal_date = subscription.renewal_date
        self.session.commit()
        self.session.refresh(subscription)
        self.session.refresh(user)
        self.billing_service.record_event(user_id, "plan_change", details={"planCode": plan.code})
        return self.get_subscription(user_id)


class UsageService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()
        self.plan_service = PlanService(self.session)
        self._usage_cache: dict[int, tuple[float, dict[str, Any]]] = {}

    def get_usage_summary(self, user_id: int) -> dict[str, Any]:
        now = time.time()
        cached = self._usage_cache.get(user_id)
        if cached and now - cached[0] < 30:
            return cached[1]

        user = self.session.query(User).get(user_id)
        if not user:
            raise AppError("User not found", status_code=404, error_code="user_not_found")
        monthly_usage = self._get_or_create_monthly_usage(user_id)
        plan = self.plan_service.get_effective_plan(user)
        remaining_uploads = self._remaining_limit(monthly_usage.uploads_used, plan.max_uploads_per_month)
        remaining_pages = self._remaining_limit(monthly_usage.pages_processed, plan.max_pages_per_month)
        summary = {
            "currentPlan": plan.code,
            "uploadsUsed": monthly_usage.uploads_used,
            "pagesUsed": monthly_usage.pages_processed,
            "downloads": monthly_usage.excel_downloads + monthly_usage.csv_downloads,
            "storageUsedBytes": monthly_usage.storage_consumed_bytes,
            "storageUsedMb": round(monthly_usage.storage_consumed_bytes / (1024 * 1024), 2),
            "remainingUploads": remaining_uploads,
            "remainingPages": remaining_pages,
            "monthlyUsage": {
                "uploads": monthly_usage.uploads_used,
                "pages": monthly_usage.pages_processed,
                "excelDownloads": monthly_usage.excel_downloads,
                "csvDownloads": monthly_usage.csv_downloads,
                "processingTimeSeconds": monthly_usage.processing_time_seconds,
            },
            "planLimit": {
                "maxUploadsPerMonth": plan.max_uploads_per_month,
                "maxPagesPerMonth": plan.max_pages_per_month,
                "maxUploadSizeMb": plan.max_upload_size_mb,
            },
        }
        self._usage_cache[user_id] = (now, summary)
        return summary

    def enforce_upload_quota(self, user_id: int, *, size_bytes: int, pages: int) -> dict[str, Any]:
        user = self.session.query(User).get(user_id)
        if not user:
            raise AppError("User not found", status_code=404, error_code="user_not_found")

        if user.subscription_status not in {None, "active"}:
            return {
                "success": False,
                "errorCode": "SUBSCRIPTION_INACTIVE",
                "message": "Subscription is not active.",
                "recommendedPlan": "PRO",
            }

        plan = self.plan_service.get_effective_plan(user)
        monthly_usage = self._get_or_create_monthly_usage(user_id)
        max_upload_size_bytes = None if plan.max_upload_size_mb is None else plan.max_upload_size_mb * 1024 * 1024
        if max_upload_size_bytes is not None and size_bytes > max_upload_size_bytes:
            return {
                "success": False,
                "errorCode": "PLAN_LIMIT_REACHED",
                "message": "Upload size exceeds the current plan limit.",
                "recommendedPlan": self.plan_service.get_recommended_plan(plan.code, size_bytes=size_bytes),
            }

        remaining_uploads = self._remaining_limit(monthly_usage.uploads_used, plan.max_uploads_per_month)
        remaining_pages = self._remaining_limit(monthly_usage.pages_processed, plan.max_pages_per_month)
        if remaining_uploads is not None and remaining_uploads <= 0:
            return {
                "success": False,
                "errorCode": "PLAN_LIMIT_REACHED",
                "message": "Monthly upload limit exceeded.",
                "recommendedPlan": self.plan_service.get_recommended_plan(plan.code),
            }
        if remaining_pages is not None and pages > remaining_pages:
            return {
                "success": False,
                "errorCode": "PLAN_LIMIT_REACHED",
                "message": "Monthly page limit exceeded.",
                "recommendedPlan": self.plan_service.get_recommended_plan(plan.code),
            }

        return {
            "success": True,
            "message": "Quota available.",
            "remainingUploads": remaining_uploads,
            "remainingPages": remaining_pages,
            "allowedUploadSizeMb": plan.max_upload_size_mb if plan.max_upload_size_mb is not None else MAX_UPLOAD_SIZE_MB,
        }

    def record_upload(self, user_id: int, *, size_bytes: int) -> MonthlyUsage:
        usage = self._get_or_create_monthly_usage(user_id)
        usage.uploads_used += 1
        usage.storage_consumed_bytes += size_bytes
        self.session.commit()
        self._invalidate_cache(user_id)
        return usage

    def record_page_processing(self, user_id: int, *, page_count: int, processing_seconds: float = 0.0) -> MonthlyUsage:
        usage = self._get_or_create_monthly_usage(user_id)
        usage.pages_processed += page_count
        usage.processing_time_seconds += int(processing_seconds)
        self.session.commit()
        self._invalidate_cache(user_id)
        return usage

    def record_excel_download(self, user_id: int) -> MonthlyUsage:
        usage = self._get_or_create_monthly_usage(user_id)
        usage.excel_downloads += 1
        self.session.commit()
        self._invalidate_cache(user_id)
        return usage

    def record_csv_download(self, user_id: int) -> MonthlyUsage:
        usage = self._get_or_create_monthly_usage(user_id)
        usage.csv_downloads += 1
        self.session.commit()
        self._invalidate_cache(user_id)
        return usage

    def _get_or_create_monthly_usage(self, user_id: int) -> MonthlyUsage:
        now = datetime.now(timezone.utc)
        usage = (
            self.session.query(MonthlyUsage)
            .filter(MonthlyUsage.user_id == user_id, MonthlyUsage.year == now.year, MonthlyUsage.month == now.month)
            .first()
        )
        if usage:
            return usage
        usage = MonthlyUsage(user_id=user_id, year=now.year, month=now.month, uploads_used=0, pages_processed=0, excel_downloads=0, csv_downloads=0, storage_consumed_bytes=0, processing_time_seconds=0, last_reset_at=now)
        self.session.add(usage)
        self.session.commit()
        self.session.refresh(usage)
        return usage

    def _remaining_limit(self, used: int, limit: int | None) -> int | None:
        if limit is None:
            return None
        return max(limit - used, 0)

    def _invalidate_cache(self, user_id: int) -> None:
        self._usage_cache.pop(user_id, None)


class BillingService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session or SessionLocal()

    def get_billing_history(self, user_id: int) -> list[dict[str, Any]]:
        events = self.session.query(BillingEvent).filter(BillingEvent.user_id == user_id).order_by(BillingEvent.occurred_at.desc()).all()
        updated = False
        for event in events:
            if event.occurred_at is None:
                event.occurred_at = datetime.utcnow()
                updated = True
        if updated:
            self.session.commit()
        return [self._serialize_event(event) for event in events]

    def record_event(self, user_id: int, event_type: str, *, amount: float | None = None, currency: str = "USD", status: str = "completed", reference_id: str | None = None, details: dict[str, Any] | None = None) -> BillingEvent:
        event = BillingEvent(
            user_id=user_id,
            event_type=event_type,
            amount=amount or 0.0,
            currency=currency,
            status=status,
            reference_id=reference_id or f"{event_type}-{datetime.utcnow().timestamp()}",
            occurred_at=datetime.utcnow(),
            details=json.dumps(details or {}),
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def _serialize_event(self, event: BillingEvent) -> dict[str, Any]:
        details = {}
        if event.details:
            try:
                details = json.loads(event.details)
            except json.JSONDecodeError:
                details = {"raw": event.details}
        occurred_at = event.occurred_at or datetime.utcnow()
        return {
            "id": event.id,
            "eventType": event.event_type,
            "amount": event.amount,
            "currency": event.currency,
            "status": event.status,
            "referenceId": event.reference_id,
            "occurredAt": occurred_at.isoformat(),
            "details": details,
        }
