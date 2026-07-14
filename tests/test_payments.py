import hmac
import hashlib
import uuid

from auth.models import User
from auth.schemas import RegisterRequest
from auth.service import AuthService
from core.settings import settings
from database.models import Payment
from services.payments import PaymentService


def _create_user() -> User:
    email = f"payment-{uuid.uuid4().hex[:8]}@example.com"
    service = AuthService()
    service.register(RegisterRequest(name="Payment User", email=email, password="secret123"))
    return service.session.query(User).filter(User.email == email).first()


def test_create_order_and_verify_payment_flow() -> None:
    user = _create_user()
    payment_service = PaymentService()

    created = payment_service.create_order(user_id=user.id, plan_code="PRO", amount=499)

    assert created["orderId"]
    assert created["amount"] == 499

    payment_id = "pay_test_123"
    order_id = created["orderId"]
    signature = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    verified = payment_service.verify_payment(
        user_id=user.id,
        payload={
            "signature": signature,
            "paymentId": payment_id,
            "orderId": order_id,
            "planCode": "PRO",
        },
    )

    assert verified["success"] is True
    stored_payment = payment_service.session.query(Payment).filter(Payment.order_id == created["orderId"]).first()
    assert stored_payment is not None
    assert stored_payment.status == "captured"


def test_payment_history_lists_user_payments() -> None:
    user = _create_user()
    payment_service = PaymentService()

    payment_service.create_order(user_id=user.id, plan_code="PRO", amount=499)
    history = payment_service.get_history(user.id)

    assert len(history) >= 1
    assert history[0]["amount"] == 499


def test_subscription_billing_status_is_paid_after_payment_verification() -> None:
    user = _create_user()
    payment_service = PaymentService()

    created = payment_service.create_order(user_id=user.id, plan_code="PRO", amount=499)
    payment_id = "pay_test_123"
    order_id = created["orderId"]
    signature = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    payment_service.verify_payment(
        user_id=user.id,
        payload={
            "signature": signature,
            "paymentId": payment_id,
            "orderId": order_id,
            "planCode": "PRO",
        },
    )

    subscription_summary = SubscriptionService(payment_service.session).get_subscription(user.id)
    assert subscription_summary["billingStatus"] == "paid"
    assert subscription_summary["subscriptionStatus"] == "active"
