from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

try:
    from razorpay import Client as RazorpayClient
except Exception:  # pragma: no cover - optional dependency
    RazorpayClient = None

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from auth.models import User
from core.settings import settings
from database.models import Invoice, Payment, Transaction, UserSubscription
from database.session import SessionLocal
from services.subscription import BillingService, SubscriptionService, UsageService


class PaymentService:
    def __init__(self, session: Session | None = None) -> None:
        # Accept an injected session; if none provided create one but ensure callers close it.
        self._owns_session = session is None
        self.session = session or SessionLocal()
        # Pass the same managed session to related services to avoid creating nested sessions
        self.subscription_service = SubscriptionService(self.session)
        self.usage_service = UsageService(self.session)
        self.billing_service = BillingService(self.session)
        self.razorpay_client = None
        if RazorpayClient and settings.razorpay_key_id and settings.razorpay_key_secret:
            self.razorpay_client = RazorpayClient(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

    def create_order(self, *, user_id: int, plan_code: str, amount: float) -> dict[str, Any]:
        try:
            user = self.session.query(User).get(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            amount_value = int(amount or 0)
            if amount_value <= 0:
                amount_value = self._plan_amount(plan_code)

            order_id = f"order_{uuid.uuid4().hex[:12]}"
            if self.razorpay_client:
                try:
                    order_payload = self.razorpay_client.order.create({
                        "amount": amount_value * 100,
                        "currency": "INR",
                        "receipt": f"receipt_{uuid.uuid4().hex[:8]}",
                        "notes": {"planCode": plan_code.upper(), "userId": str(user_id)},
                    })
                    order_id = str(order_payload.get("id", order_id))
                except Exception:
                    order_id = order_id

            payment = Payment(
                user_id=user_id,
                order_id=order_id,
                amount=float(amount_value),
                currency="INR",
                status="created",
                plan_code=plan_code.upper(),
                method="razorpay",
                created_at=datetime.utcnow(),
            )
            self.session.add(payment)
            self.session.commit()
            self.session.refresh(payment)

            return {
                "orderId": payment.order_id,
                "amount": int(payment.amount),
                "currency": payment.currency,
                "keyId": settings.razorpay_key_id or "test_key",
                "planCode": payment.plan_code,
                "status": payment.status,
            }
        finally:
            if self._owns_session:
                try:
                    self.session.close()
                except Exception:
                    pass

    def verify_payment(self, *, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            order_id = str(
                payload.get("razorpay_order_id")
                or payload.get("orderId")
                or ""
            )

            payment_id = str(
                payload.get("razorpay_payment_id")
                or payload.get("paymentId")
                or ""
            )

            signature = str(
                payload.get("razorpay_signature")
                or payload.get("signature")
                or ""
            )
            plan_code = str(payload.get("planCode") or "PRO")

            payment = self.session.query(Payment).filter(Payment.order_id == order_id).first()
            if not payment:
                raise HTTPException(status_code=404, detail="Payment order not found")
            if payment.user_id != user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
            if payment.status == "captured":
                return {"success": True, "message": "Payment already verified", "paymentId": payment.payment_id}

            if not self._verify_signature(order_id=order_id, payment_id=payment_id, signature=signature):
                payment.status = "failed"
                self.session.commit()
                return {"success": False, "message": "Invalid signature"}

            payment.payment_id = payment_id
            payment.status = "captured"
            payment.completed_at = datetime.utcnow()
            self.session.commit()

            self._activate_subscription(user_id=user_id, plan_code=plan_code, payment=payment)
            self._create_invoice(payment)
            self._record_transaction(payment, transaction_id=payment_id, status="success")
            self.billing_service.record_event(user_id, "payment_captured", amount=float(payment.amount), currency=payment.currency, status="completed", reference_id=payment.order_id, details={"planCode": plan_code.upper()})

            return {"success": True, "message": "Payment verified", "paymentId": payment.payment_id, "orderId": payment.order_id}
        finally:
            if self._owns_session:
                try:
                    self.session.close()
                except Exception:
                    pass

    async def handle_webhook(self, request: Request) -> dict[str, Any]:
        body = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        payload = body.decode("utf-8")
        if not self._verify_webhook_signature(payload=payload, signature=signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

        data = json.loads(payload)
        event = data.get("event", "")
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id") or data.get("order_id") or ""
        payment_id = payment_entity.get("id") or ""
        status = payment_entity.get("status") or ""

        payment = self.session.query(Payment).filter(Payment.order_id == order_id).first()
        if not payment:
            return {"success": False, "message": "Payment order not found"}

        if event == "payment.captured":
            payment.payment_id = payment_id
            payment.status = "captured"
            payment.completed_at = datetime.utcnow()
            self.session.commit()
            self._activate_subscription(user_id=payment.user_id, plan_code=payment.plan_code, payment=payment)
            self._create_invoice(payment)
            self._record_transaction(payment, transaction_id=payment_id, status="success")
            self.billing_service.record_event(user_id=payment.user_id, event_type="payment_captured", amount=float(payment.amount), currency=payment.currency, status="completed", reference_id=payment.order_id, details={"planCode": payment.plan_code})
        elif event == "payment.failed":
            payment.status = "failed"
            self.session.commit()
            self._record_transaction(payment, transaction_id=payment_id, status="failed")
        elif event == "subscription.activated":
            self._activate_subscription(user_id=payment.user_id, plan_code=payment.plan_code, payment=payment)
        elif event == "subscription.cancelled":
            self._cancel_subscription(user_id=payment.user_id)

        # Close session if this service owns it
        if self._owns_session:
            try:
                self.session.close()
            except Exception:
                pass
        return {"success": True, "message": f"Handled {event}"}

    def get_history(self, user_id: int) -> list[dict[str, Any]]:
        try:
            payments = self.session.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).all()
            return [self._serialize_payment(payment) for payment in payments]
        finally:
            if self._owns_session:
                try:
                    self.session.close()
                except Exception:
                    pass

    def get_invoice(self, invoice_id: int, *, user_id: int) -> dict[str, Any]:
        try:
            invoice = self.session.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == user_id).first()
            if not invoice:
                raise HTTPException(status_code=404, detail="Invoice not found")
            return self._serialize_invoice(invoice)
        finally:
            if self._owns_session:
                try:
                    self.session.close()
                except Exception:
                    pass

    def _activate_subscription(self, *, user_id: int, plan_code: str, payment: Payment) -> None:
        user = self.session.query(User).get(user_id)
        if not user:
            return
        user.current_plan = plan_code.upper()
        user.subscription_status = "active"
        user.billing_status = "paid"
        user.renewal_date = datetime.utcnow() + timedelta(days=30)

        subscriptions = self.session.query(UserSubscription).filter(UserSubscription.user_id == user_id).all()
        if not subscriptions:
            subscription = UserSubscription(user_id=user_id, plan_code=plan_code.upper(), status="active", billing_status="paid", started_at=datetime.utcnow(), renewal_date=user.renewal_date)
            self.session.add(subscription)
        else:
            for subscription in subscriptions:
                subscription.plan_code = plan_code.upper()
                subscription.status = "active"
                subscription.billing_status = "paid"
                subscription.renewal_date = user.renewal_date

        self.session.commit()
        self.billing_service.record_event(user_id, "subscription_activated", amount=float(payment.amount), currency=payment.currency, status="completed", reference_id=payment.order_id, details={"planCode": plan_code.upper()})
        self.usage_service._invalidate_cache(user_id)

    def _cancel_subscription(self, *, user_id: int) -> None:
        user = self.session.query(User).get(user_id)
        if user:
            user.subscription_status = "cancelled"
            user.billing_status = "cancelled"
            self.session.commit()

    def _create_invoice(self, payment: Payment) -> None:
        invoice = self.session.query(Invoice).filter(Invoice.payment_id == payment.id).first()
        if invoice:
            invoice.status = "paid" if payment.status == "captured" else "issued"
            invoice.paid_at = datetime.utcnow() if payment.status == "captured" else None
            invoice.issued_at = invoice.issued_at or datetime.utcnow()
        else:
            invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{payment.id:04d}"
            invoice = Invoice(
                invoice_number=invoice_number,
                payment_id=payment.id,
                user_id=payment.user_id,
                plan_code=payment.plan_code,
                amount=payment.amount,
                currency=payment.currency,
                status="paid" if payment.status == "captured" else "issued",
                issued_at=datetime.utcnow(),
                paid_at=datetime.utcnow() if payment.status == "captured" else None,
            )
            self.session.add(invoice)
        self.session.commit()

    def _record_transaction(self, payment: Payment, *, transaction_id: str, status: str) -> None:
        transaction = Transaction(
            payment_id=payment.id,
            user_id=payment.user_id,
            gateway="razorpay",
            transaction_id=transaction_id,
            amount=payment.amount,
            currency=payment.currency,
            status=status,
            response_code="ok" if status == "success" else "failed",
            created_at=datetime.utcnow(),
            metadata_json=json.dumps({"orderId": payment.order_id}),
        )
        self.session.add(transaction)
        self.session.commit()

    def _verify_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        if not settings.razorpay_key_secret:
            return True
        expected = hmac.new(settings.razorpay_key_secret.encode("utf-8"), f"{order_id}|{payment_id}".encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def _verify_webhook_signature(self, *, payload: str, signature: str) -> bool:
        if not settings.razorpay_key_secret:
            return True
        return hmac.compare_digest(signature, hmac.new(settings.razorpay_key_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest())

    def _plan_amount(self, plan_code: str) -> int:
        mapping = {"FREE": 0, "PRO": 499, "ENTERPRISE": 1499}
        return mapping.get(plan_code.upper(), 499)

    def _serialize_payment(self, payment: Payment) -> dict[str, Any]:
        invoice = self.session.query(Invoice).filter(Invoice.payment_id == payment.id).first()
        return {
            "id": payment.id,
            "orderId": payment.order_id,
            "paymentId": payment.payment_id,
            "amount": int(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "plan": payment.plan_code,
            "invoice": self._serialize_invoice(invoice) if invoice else None,
            "createdAt": payment.created_at.isoformat() if payment.created_at else None,
            "completedAt": payment.completed_at.isoformat() if payment.completed_at else None,
        }

    def _serialize_invoice(self, invoice: Invoice | None) -> dict[str, Any] | None:
        if not invoice:
            return None
        return {
            "id": invoice.id,
            "invoiceNumber": invoice.invoice_number,
            "amount": int(invoice.amount),
            "currency": invoice.currency,
            "status": invoice.status,
            "issuedAt": invoice.issued_at.isoformat() if invoice.issued_at else None,
            "paidAt": invoice.paid_at.isoformat() if invoice.paid_at else None,
        }
